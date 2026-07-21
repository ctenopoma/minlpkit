"""cuOpt(GPU) による warm start 注入 (WSL2 + PySCIPOpt)。

「GPUは可行解探索、CPUは証明」という分業を1関数に閉じ込めたもの。cuOpt を短時間走らせて
可行解を掘り、それを SCIP へ ``addSol`` で注入してから通常どおり ``optimize()`` させる、
という使い方を想定する(cuOpt自身は最適性証明をしないので下界の改善はSCIP側に委ねる)。

前提: WSL2 上に Ubuntu ディストリビューションがあり、cuOpt (cuopt-cu13) が導入済みで
GPU が WSL から見えること。実行ファイルは既定で ``/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli``
(WSL側パス)。ネイティブ Linux 環境では ``cuopt_cmd=["cuopt_cli"]`` のように prefix に
"wsl" を含めない指定を渡せば、Windows→WSL のパス変換をスキップしてそのまま実行する。

cuOpt の出力 .sol は SCIP 互換形式(``変数名 値`` 行 + ``#`` コメント)なので
``model.readSolFile`` でそのまま読める。可行解が見つからなかった場合、.sol は
目的値ゼロ埋めのダミーになる(ログに ``Solution objective: ...`` 行が出ない)ため、
この関数はログを見て可行解の有無を判定し、無ければ注入をスキップする。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from pyscipopt import SCIP_EVENTTYPE, Eventhdlr, Model

# --- HTTP (self-hosted cuOpt server) バックエンド ------------------------------
# NVIDIA cuOpt self-hosted server(Dockerコンテナ / cuopt-server pip)の LP/MILP
# REST API に準拠する。公式クライアント(cuopt-sh-client)はMPSをクライアント側で
# cuOpt データモデルJSONへパースし ``POST /cuopt/request`` する(生MPSを受け付ける
# HTTPエンドポイントは存在しない)。本実装も同じデータモデルJSONを PySCIPOpt の
# 線形構造から直接組み立てて送る(cuopt_mps_parser 依存を避けるため)。
# 出典: https://docs.nvidia.com/cuopt/user-guide/latest/cuopt-server/  (25.10)
#       https://github.com/NVIDIA/cuopt (python/cuopt_self_hosted/cuopt_sh_client)
_ENV_URL = "MINLPKIT_CUOPT_URL"

# cuOpt サーバが可行/最適を示す status 文字列(これ以外は注入しない)
_FEASIBLE_STATUS = ("Optimal", "Feasible", "FeasibleFound")

# JSON は Infinity を表現できないため、無限境界はこのセンチネルに丸める(LP/MPS 慣習の
# 「大きい有限値=無限」。実サーバでの厳密な無限表現は未検証=E2E持ち越し、FINDINGS §7参照)
_INF_SENTINEL = 1e20

_DEFAULT_CUOPT_CMD = ["wsl", "-d", "Ubuntu", "--",
                       "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]

# cuOptログの最終サマリ行: "Solution objective: <obj> , relative_mip_gap <gap> solution_bound <bound>"
_SUMMARY = re.compile(
    r"Solution objective:\s*([-\d.eE+]+)\s*,\s*relative_mip_gap\s*([-\d.eE+]+)"
    r"\s*solution_bound\s*([-\d.eE+]+)")

_INSTALL_HINT = (
    "cuOpt が見つからない。GPU機能は任意(未導入でもminlpkit本体は完全動作)。"
    "導入する場合は WSL2 Ubuntu 側で:\n"
    "  uv venv --python 3.12 ~/cuopt-env && "
    "VIRTUAL_ENV=~/cuopt-env uv pip install "
    "--extra-index-url=https://pypi.nvidia.com 'cuopt-cu13==25.10.*'\n"
    "詳細は docs/manual/gpu-setup.md(GPU warm start)。導入確認は mk.cuopt_available()。")

def _http_hint(server_url: str, detail: str = "") -> str:
    """HTTPバックエンドの接続失敗時の案内(サーバ起動docker手順を1行含む)。"""
    tail = f"\n詳細: {detail}" if detail else ""
    return (
        f"cuOpt サーバ({server_url})に接続できない。GPUサーバ側で公式コンテナを起動:\n"
        "  docker run --gpus all --rm -p 8000:8000 -e CUOPT_SERVER_PORT=8000 "
        "nvcr.io/nvidia/cuopt/cuopt:25.10\n"
        f"クライアントは環境変数 {_ENV_URL}=http://<server>:8000 か server_url= で指す。"
        "健全性は GET /cuopt/health、詳細は docs/manual/gpu-setup.md(リモートサーバ構成)。"
        + tail)


_availability_cache: dict[tuple, bool] = {}


def _resolve_server_url(server_url: Optional[str]) -> Optional[str]:
    """server_url の解決順: 引数 > 環境変数 ``MINLPKIT_CUOPT_URL`` > None(=CLI経路)。"""
    if server_url is not None:
        return server_url
    env = os.environ.get(_ENV_URL)
    return env if env else None


def _http_get_json(url: str, timeout: float) -> tuple[int, object]:
    """GET してステータスコードとJSONボディ(パース不能ならテキスト)を返す。"""
    req = urllib.request.Request(url, method="GET",
                                 headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
        try:
            return r.status, json.loads(body)
        except json.JSONDecodeError:
            return r.status, body


def _http_post_json(url: str, payload: dict, timeout: float) -> object:
    """cuOpt データモデルJSONを ``POST /cuopt/request`` 相当へ送りJSONを返す。"""
    data = json.dumps(payload).encode("utf-8")
    # CLIENT-VERSION は公式クライアントが送るヘッダ。任意サーバ互換のため "custom" を使う
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "CLIENT-VERSION": "custom"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))


def _server_health_ok(server_url: str, timeout: float = 10.0) -> bool:
    """``GET /cuopt/health`` が 200 を返すか。接続不能・非200は False。"""
    try:
        status, _ = _http_get_json(server_url.rstrip("/") + "/cuopt/health", timeout)
        return status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def _model_to_datamodel(model: Model, time_limit: float) -> dict:
    """PySCIPOpt の線形MILPを cuOpt LP/MILP データモデルJSON(dict)へ変換する。

    cuOpt server の ``POST /cuopt/request`` が受ける LPData スキーマ(CSR行列 +
    変数/制約境界 + variable_types)に対応。非線形制約を含む場合は RuntimeError
    (cuOpt は MILP専用。既定CLI経路の writeProblem→MPS も同様に線形前提)。
    """
    variables = list(model.getVars())
    var_index = {v.name: i for i, v in enumerate(variables)}

    def _clamp(x: float) -> float:
        if x >= model.infinity():
            return _INF_SENTINEL
        if x <= -model.infinity():
            return -_INF_SENTINEL
        return float(x)

    var_lb = [_clamp(v.getLbGlobal()) for v in variables]
    var_ub = [_clamp(v.getUbGlobal()) for v in variables]
    # BINARY/INTEGER/IMPLINT → "I"、CONTINUOUS → "C"
    var_types = ["C" if v.vtype() == "CONTINUOUS" else "I" for v in variables]
    obj_coefs = [float(v.getObj()) for v in variables]

    offsets = [0]
    indices: list[int] = []
    values: list[float] = []
    con_lb: list[float] = []
    con_ub: list[float] = []
    for cons in model.getConss():
        if cons.getConshdlrName() != "linear":
            raise RuntimeError(
                "cuOpt HTTPバックエンドは線形MILP専用。非線形制約 "
                f"'{cons.name}'(handler={cons.getConshdlrName()})は送れない。"
                "cuOpt自体がMILP専用のため、非線形モデルはSCIP単体で解くこと。")
        coefs = model.getValsLinear(cons)  # {変数名: 係数}
        for name, coef in coefs.items():
            indices.append(var_index[name])
            values.append(float(coef))
        offsets.append(len(indices))
        con_lb.append(_clamp(model.getLhs(cons)))
        con_ub.append(_clamp(model.getRhs(cons)))

    try:
        obj_offset = float(model.getObjoffset())
    except Exception:
        obj_offset = 0.0

    return {
        "csr_constraint_matrix": {"offsets": offsets, "indices": indices,
                                  "values": values},
        "constraint_bounds": {"upper_bounds": con_ub, "lower_bounds": con_lb},
        "objective_data": {"coefficients": obj_coefs, "scalability_factor": 1.0,
                           "offset": obj_offset},
        "variable_bounds": {"upper_bounds": var_ub, "lower_bounds": var_lb},
        "maximize": model.getObjectiveSense().lower().startswith("max"),
        "variable_types": var_types,
        "variable_names": [v.name for v in variables],
        "solver_config": {"time_limit": time_limit},
    }


def _extract_http_solution(resp: dict) -> dict:
    """cuOpt サーバ応答から目的値・変数値・status・下界・gapを取り出す。

    応答形: ``resp["response"]["solver_response"]`` に ``status`` と ``solution``
    (``vars`` 名→値の辞書、``primal_objective``、任意で ``milp_statistics``)。
    """
    solver_response = resp.get("response", {}).get("solver_response", {})
    if isinstance(solver_response, list):  # バッチ(LPのみ)は先頭を採る
        solver_response = solver_response[0] if solver_response else {}
    solution = solver_response.get("solution", {}) or {}
    stats = solution.get("milp_statistics", {}) or {}
    return {
        "status": solver_response.get("status"),
        "vars": solution.get("vars") or {},
        "objective": solution.get("primal_objective"),
        "bound": stats.get("solution_bound"),
        "gap": stats.get("mip_gap"),
    }


def _cuopt_http_solve(model: Model, time_limit: float, server_url: str, *,
                      poll_interval: float, timeout: float) -> dict:
    """cuOpt サーバに1問投げ、(必要ならポーリングして)解結果 dict を返す。

    ``POST /cuopt/request`` → 応答が ``{"reqId": ...}`` のみなら pending として
    ``GET /cuopt/solution/{reqId}`` を ``poll_interval`` 秒間隔でポーリングする
    (公式クライアントと同じ非同期契約)。
    """
    base = server_url.rstrip("/")
    payload = _model_to_datamodel(model, time_limit)
    try:
        resp = _http_post_json(base + "/cuopt/request", payload, timeout=timeout)
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(_http_hint(server_url, str(e))) from e

    deadline = time.time() + timeout
    # reqId だけの応答は「まだpending」(公式クライアント準拠の判定)
    while isinstance(resp, dict) and len(resp) == 1 and "reqId" in resp:
        if time.time() > deadline:
            raise RuntimeError(
                f"cuOpt サーバのポーリングがタイムアウト(reqId={resp['reqId']})。")
        time.sleep(poll_interval)
        try:
            _, resp = _http_get_json(base + "/cuopt/solution/" + str(resp["reqId"]),
                                     timeout=timeout)
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(_http_hint(server_url, str(e))) from e

    if not isinstance(resp, dict) or "response" not in resp:
        raise RuntimeError(
            f"cuOpt サーバがエラー応答を返した: {json.dumps(resp)[:500]}")
    return _extract_http_solution(resp)


def _write_scip_sol(path: Path, sol: dict) -> None:
    """cuOpt サーバ解を SCIP 互換 .sol(# コメント + ``変数名 値``)へ書き出す。

    ``# Status:`` / ``# Objective value:`` ヘッダは常駐型の ``_parse_sol_file`` が
    参照する形に合わせる(直列warmstart は ``readSolFile`` がコメントを無視して読む)。
    """
    lines = [f"# Status: {sol.get('status')}",
             f"# Objective value: {sol.get('objective')}"]
    lines += [f"{name} {val}" for name, val in sol["vars"].items()]
    path.write_text("\n".join(lines) + "\n")


def cuopt_available(cuopt_cmd: Optional[list[str]] = None, *,
                    server_url: Optional[str] = None) -> bool:
    """cuOpt が使えるか(HTTPサーバのヘルスチェック or WSL2/CLIの実行可否)を返す。

    minlpkit のGPU機能は完全に任意で、追加のPython依存も持たない(HTTPは標準ライブラリ
    urllib、CLI経路のcuOpt本体はWSL2側の別venv)。未導入環境でも import・診断は通常
    どおり動くので、``cuopt_warmstart``/``cuopt_concurrent`` を呼ぶ前の分岐にこの関数を
    使う。結果はプロセス内でキャッシュされる(HTTPはURL別、CLIはコマンド別)。

    解決順は ``server_url`` 引数 > 環境変数 ``MINLPKIT_CUOPT_URL`` > CLI。前二者が
    解決されればHTTPバックエンドとみなし ``GET /cuopt/health`` を叩く。

    Args:
        cuopt_cmd: CLI経路のコマンド prefix。既定はWSL2経由。
        server_url: cuOpt self-hosted サーバのベースURL(例 ``http://192.168.50.37:8000``)。
            省略時は環境変数 ``MINLPKIT_CUOPT_URL`` を見る。解決されればHTTP経路。

    Returns:
        bool: HTTP経路なら ``/cuopt/health`` が200、CLI経路なら cuopt_cli が起動可能で True。

    Example:
        >>> import minlpkit as mk
        >>> mk.cuopt_available(server_url="http://127.0.0.1:1")  # 未起動ポート
        False
    """
    url = _resolve_server_url(server_url)
    if url is not None:
        key: tuple = ("http", url.rstrip("/"))
        if key in _availability_cache:
            return _availability_cache[key]
        ok = _server_health_ok(url)
        _availability_cache[key] = ok
        return ok

    cmd_prefix = list(cuopt_cmd) if cuopt_cmd is not None else list(_DEFAULT_CUOPT_CMD)
    key = tuple(cmd_prefix)
    if key in _availability_cache:
        return _availability_cache[key]
    is_wsl = bool(cmd_prefix) and cmd_prefix[0] == "wsl"
    try:
        if is_wsl:
            proc = subprocess.run(cmd_prefix[:-1] + ["test", "-x", cmd_prefix[-1]],
                                  capture_output=True, timeout=30)
            ok = proc.returncode == 0
        else:
            import shutil
            ok = shutil.which(cmd_prefix[0]) is not None
    except (OSError, subprocess.TimeoutExpired):
        ok = False
    _availability_cache[key] = ok
    return ok


def _to_wsl_path(p: Path) -> str:
    """Windows パス ``D:\\foo\\bar`` を WSL パス ``/mnt/d/foo/bar`` へ変換する。"""
    s = str(p.resolve())
    drive, rest = s[0].lower(), s[2:].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def _stage_mps_native(cmd_prefix: list[str], mps_path: Path) -> str:
    """MPSをWSLネイティブFS(/tmp)へコピーし、コピー先のWSLパスを返す。

    cuopt_cli が ``/mnt/<drive>``(9pファイルシステム)上のMPSを直接読むと、
    大きいファイルで読み込みが極端に遅い(gap_large 15MBで実測+約20秒)。
    ネイティブFSに1回コピーしてから読ませると解消する。コピー自体はシーケンシャル
    書き込みなので安価。``cmd_prefix`` は ``["wsl", "-d", <distro>, "--", <cli>]`` 形式を想定し、
    その wsl 呼び出し部分(末尾のcliを除く)を流用して ``cp`` を実行する。
    """
    dst = f"/tmp/minlpkit_{os.getpid()}_{mps_path.name}"
    cp_cmd = cmd_prefix[:-1] + ["cp", _to_wsl_path(mps_path), dst]
    subprocess.run(cp_cmd, check=True, capture_output=True, timeout=120)
    return dst


def _fetch_from_wsl(cmd_prefix: list[str], wsl_src: str, dst: Path) -> bool:
    """WSLネイティブFS上のファイルをWindows側 ``dst`` へ1回のcpで回収する。

    cuopt_cli に ``/mnt/<drive>`` 上の ``--solution-file`` を直接書かせると、
    細かいwriteが9p越しになり大きく遅い(gap_largeの.sol 0.8MBで実測+約19秒)。
    WSL側 /tmp に書かせてから、シーケンシャルな ``cp`` 1回で回収する方が速い。
    """
    try:
        subprocess.run(cmd_prefix[:-1] + ["cp", wsl_src, _to_wsl_path(dst)],
                       check=True, capture_output=True, timeout=120)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False
    return dst.exists()


def _cuopt_warmstart_http(model: Model, time_limit: float, server_url: str, *,
                          mps_dir: Optional[str], poll_interval: float) -> dict:
    """``cuopt_warmstart`` のHTTP(self-hostedサーバ)バックエンド実体。"""
    if not cuopt_available(server_url=server_url):
        raise RuntimeError(_http_hint(server_url, "GET /cuopt/health が200を返さない"))

    workdir = Path(mps_dir) if mps_dir is not None else Path(tempfile.mkdtemp())
    workdir.mkdir(parents=True, exist_ok=True)
    # 既存CLI経路との対称性・デバッグ用に MPS も書き出す(送信ペイロードは同じ model の
    # 線形構造から組み立てるため、この MPS は成果物/検証用のスナップショット)
    model.writeProblem(str(workdir / "cuopt_warmstart.mps"))
    sol_path = workdir / "cuopt_warmstart.sol"

    t0 = time.perf_counter()
    result = _cuopt_http_solve(model, time_limit, server_url,
                               poll_interval=poll_interval,
                               timeout=time_limit + 120)
    wall = time.perf_counter() - t0

    accepted = False
    if result["vars"] and result.get("status") in _FEASIBLE_STATUS:
        _write_scip_sol(sol_path, result)
        sol = model.readSolFile(str(sol_path))
        accepted = model.addSol(sol)

    return dict(objective=result["objective"], bound=result["bound"],
                gap=result["gap"], accepted=accepted, wall_time=wall,
                log=json.dumps(result, default=str))


def cuopt_warmstart(model: Model, time_limit: float = 15.0, *,
                    cuopt_cmd: Optional[list[str]] = None,
                    server_url: Optional[str] = None,
                    mps_dir: Optional[str] = None,
                    heuristics_only: bool = False,
                    num_cpu_threads: Optional[int] = None,
                    poll_interval: float = 1.0) -> dict:
    """cuOpt(GPU)で短時間探索し、見つかった可行解を model に warm start として注入する。

    2つのバックエンドがある。``server_url``(または環境変数 ``MINLPKIT_CUOPT_URL``)が
    解決されれば **HTTPバックエンド**: model の線形構造を cuOpt LP/MILP データモデルJSON
    へ変換して self-hosted サーバの ``POST /cuopt/request`` に送り(非同期なら
    ``GET /cuopt/solution/{reqId}`` をポーリング)、返った変数値を SCIP互換 .sol 化して
    ``readSolFile`` + ``addSol`` で注入する。解決されなければ従来どおり **CLIバックエンド**:
    ``model`` を MPS に書き出して WSL2 上の cuOpt CLI に渡し、標準出力ログから目的値・
    下界・ギャップを読み取り ``.sol`` を注入する。呼び出しは ``model.optimize()`` より前に
    行うこと(最適化中/後のモデルへ注入しても意味がない)。

    Args:
        model: PySCIPOpt Model。最適化前のもの(``writeProblem`` できる状態)。
        time_limit: cuOpt に渡す時間制限[秒]。CLIではサブプロセスのタイムアウトが
            ``time_limit + 120`` 秒、HTTPではポーリングのデッドラインが同値。
        cuopt_cmd: CLI経路の cuopt_cli 起動コマンド prefix。既定は
            ``["wsl", "-d", "Ubuntu", "--", "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]``。
            prefix 先頭が ``"wsl"`` でなければネイティブ実行(パス変換なし)。
        server_url: cuOpt self-hosted サーバのベースURL(例 ``http://192.168.50.37:8000``)。
            指定するとHTTPバックエンドになる。省略時は環境変数 ``MINLPKIT_CUOPT_URL`` を見る。
        mps_dir: 一時MPS/.solの出力先ディレクトリ。省略時は ``tempfile.mkdtemp()``。
            CLIではWSL側から見える(Windowsの通常ドライブ上の)ディレクトリが必要。
        heuristics_only: (CLIのみ)True で ``--mip-heuristics-only true`` を渡す。
        num_cpu_threads: (CLIのみ)cuOpt のCPU側B&Bスレッド数(``--num-cpu-threads``)。
        poll_interval: (HTTPのみ)``/cuopt/solution`` のポーリング間隔[秒]。

    Returns:
        dict: ``objective``(cuOptが見つけた目的値。可行解無しなら None)、
        ``bound``(cuOptの下界)、``gap``(相対ギャップ)、
        ``accepted``(``model.addSol`` が受理したか。可行解が無ければ False)、
        ``wall_time``(cuOpt呼び出しの実測秒数)、``log``(CLIは標準出力全文、HTTPは応答JSON)。

    Raises:
        RuntimeError: HTTP経路でサーバに接続できない/エラー応答の場合(docker起動手順つき)、
            または CLI経路で cuopt_cli がゼロ以外の終了コードを返した場合(末尾ログ付き)。

    Note:
        cuOptは最適性証明をしない(下界はヒューリスティックな推定に留まる)ため、
        本関数の役割は「可行解の種をSCIPに渡す」ことに限る。証明はSCIPの通常の
        ``optimize()`` に委ねる想定(cuOpt=可行解探索、SCIP=証明、の分業)。
        HTTPバックエンドは cuOpt が MILP専用のため線形MILPのみ対応(非線形制約は
        RuntimeError)。参考実装: ``experiments/run_gpu_heuristic.py``、
        疎通確認: ``experiments/check_cuopt_server.py``。

    Example:
        ```python
        import os, minlpkit as mk
        os.environ["MINLPKIT_CUOPT_URL"] = "http://192.168.50.37:8000"
        m = build_model()                     # 線形MILP、最適化前
        res = mk.cuopt_warmstart(m, time_limit=15)
        print(res["objective"], res["accepted"])
        m.setParam("limits/time", 60); m.optimize()
        ```
    """
    url = _resolve_server_url(server_url)
    if url is not None:
        return _cuopt_warmstart_http(model, time_limit, url, mps_dir=mps_dir,
                                     poll_interval=poll_interval)

    cmd_prefix = list(cuopt_cmd) if cuopt_cmd is not None else list(_DEFAULT_CUOPT_CMD)
    is_wsl = bool(cmd_prefix) and cmd_prefix[0] == "wsl"
    if not cuopt_available(cmd_prefix):
        raise RuntimeError(_INSTALL_HINT)

    workdir = Path(mps_dir) if mps_dir is not None else Path(tempfile.mkdtemp())
    workdir.mkdir(parents=True, exist_ok=True)
    mps_path = workdir / "cuopt_warmstart.mps"
    sol_path = workdir / "cuopt_warmstart.sol"

    model.writeProblem(str(mps_path))

    # WSL経由なら9pの遅さを避け、MPS読み・.sol書きともネイティブFS(/tmp)で行う
    mps_arg = _stage_mps_native(cmd_prefix, mps_path) if is_wsl else str(mps_path)
    sol_arg = (f"/tmp/minlpkit_{os.getpid()}_{sol_path.name}" if is_wsl
               else str(sol_path))

    cmd = cmd_prefix + ["--time-limit", str(time_limit), "--solution-file", sol_arg]
    if heuristics_only:
        cmd += ["--mip-heuristics-only", "true"]
    if num_cpu_threads is not None:
        cmd += ["--num-cpu-threads", str(num_cpu_threads)]
    cmd.append(mps_arg)

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 120)
    wall = time.perf_counter() - t0
    log = proc.stdout
    if proc.returncode != 0:
        raise RuntimeError(
            f"cuopt_cli failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}\n{log[-2000:]}")
    if is_wsl:
        _fetch_from_wsl(cmd_prefix, sol_arg, sol_path)

    objective = bound = gap = None
    ms = _SUMMARY.search(log)
    if ms:
        objective, gap, bound = float(ms.group(1)), float(ms.group(2)), float(ms.group(3))

    accepted = False
    if objective is not None and sol_path.exists():
        sol = model.readSolFile(str(sol_path))
        accepted = model.addSol(sol)

    return dict(objective=objective, bound=bound, gap=gap,
                accepted=accepted, wall_time=wall, log=log)


def _parse_sol_file(path: Path) -> tuple[Optional[float], dict[str, float]]:
    """cuOptの .sol を読み、(ヘッダの目的値 or None, {変数名: 値}) を返す。

    可行解が無い場合のダミー .sol はヘッダが ``# Status: TimeLimit`` かつ
    ``# Objective value: 0`` になる。可行解ありは ``# Status: FeasibleFound``
    (または Optimal)なので、Status ヘッダで判別し、無可行なら (None, {}) を返す。
    """
    feasible = False
    objective: Optional[float] = None
    vals: dict[str, float] = {}
    for line in path.read_text().splitlines():
        if line.startswith("#"):
            if "Status:" in line and ("Feasible" in line or "Optimal" in line):
                feasible = True
            if "Objective value:" in line:
                try:
                    objective = float(line.split(":")[1])
                except ValueError:
                    pass
            continue
        parts = line.split()
        if len(parts) == 2:
            vals[parts[0]] = float(parts[1])
    if not feasible:
        return None, {}
    return objective, vals


class _ConcurrentInjector(Eventhdlr):
    """SCIP求解中に cuOpt サブプロセスの完了をポーリングし、解を trySol で注入する。

    NODESOLVED ごとに(``poll_interval`` 秒スロットルで)cuOpt プロセスの終了を確認し、
    終了していれば .sol を読んで ``createSol``/``setSolVal``/``trySol`` で注入する。
    SOLVINGステージ中の trySol 注入は検証済み(受理されると即 incumbent が置き換わり、
    以後の剪定に効く)。注入は1回だけ行う。
    """

    def __init__(self, proc: subprocess.Popen, sol_path: Path, poll_interval: float,
                 fetch_sol=None):
        self.proc = proc
        self.sol_path = sol_path
        self.poll_interval = poll_interval
        self.fetch_sol = fetch_sol  # WSL /tmp から .sol を回収するcallable(不要ならNone)
        self.done = False
        self.injected = False
        self.inject_time: Optional[float] = None
        self.objective: Optional[float] = None
        self._next_check = 0.0
        self.n_events = 0            # 診断: イベント発火回数(0なら注入機会が無かった)
        self.fetch_ok: Optional[bool] = None  # 診断: .sol回収の成否(未実行はNone)

    def eventinit(self):
        # NODESOLVEDだけだとルートノードの分離ループ中(数十秒かかりうる)に発火せず
        # 注入が遅れるため、ルート中も頻繁に発火する LPSOLVED を併用する(実測:
        # gap_largeでcuOpt完了13sに対しNODESOLVEDのみだと注入が60s=SCIP終了間際だった)
        self.model.catchEvent(SCIP_EVENTTYPE.NODESOLVED, self)
        self.model.catchEvent(SCIP_EVENTTYPE.LPSOLVED, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.NODESOLVED, self)
        self.model.dropEvent(SCIP_EVENTTYPE.LPSOLVED, self)

    def eventexec(self, event):
        m = self.model
        if self.done:
            return
        self.n_events += 1
        now = m.getSolvingTime()
        if now < self._next_check:
            return
        self._next_check = now + self.poll_interval
        if self.proc.poll() is None:      # cuOpt まだ実行中
            return
        self.done = True
        if self.fetch_sol is not None:
            self.fetch_ok = bool(self.fetch_sol())
            if not self.fetch_ok:
                return  # 回収失敗時に前回runの残骸solを読まない
        if not self.sol_path.exists():
            return
        objective, vals = _parse_sol_file(self.sol_path)
        if objective is None or not vals:  # 可行解なし(ダミー .sol)
            return
        varmap = {v.name: v for v in m.getVars()}
        sol = m.createSol()
        for name, val in vals.items():
            if name in varmap:
                m.setSolVal(sol, varmap[name], val)
        self.injected = bool(m.trySol(sol))
        self.inject_time = now
        self.objective = objective


class CuoptConcurrent:
    """cuOpt を SCIP と並走させる常駐型ハイブリッドのハンドル。

    ``cuopt_concurrent(model, ...)`` が返す。``model.optimize()`` の間、裏で走る
    cuOpt が終了し次第、イベントハンドラが解を SCIP へ注入する(GPU待ちの直列時間ゼロ)。
    ``optimize()`` 後に ``result()`` で注入結果を回収する。

    Example:
        ```python
        h = mk.cuopt_concurrent(m, time_limit=15)
        m.setParam("limits/time", 60)
        m.optimize()          # cuOptと並走。終了次第incumbent注入
        info = h.result()     # injected / objective / inject_time / wall_time
        ```
    """

    def __init__(self, proc: subprocess.Popen, injector: _ConcurrentInjector,
                 log_path: Path, t0: float):
        self._proc = proc
        self._injector = injector
        self._log_path = log_path
        self._t0 = t0

    def result(self) -> dict:
        """cuOptプロセスを回収し、注入結果を返す(``optimize()`` の後に呼ぶ)。

        SCIPが先に終わっていて cuOpt がまだ走っている場合は terminate する
        (warm start 目的では以後の探索結果を使う先が無いため)。

        Returns:
            dict: ``injected``(trySol が受理したか)、``objective``(注入解の目的値。
            注入なしなら None)、``inject_time``(SCIP求解時刻での注入時点[秒])、
            ``wall_time``(cuOpt起動からの実測秒数)、``log``(cuOpt標準出力全文)。
        """
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        wall = time.perf_counter() - self._t0
        log = self._log_path.read_text(errors="replace") if self._log_path.exists() else ""
        # wall(result()呼び出しまでの経過)はSCIP求解時間を含むため、cuOpt自身の
        # 実行時間はログの total_solve_time を優先する
        mt = re.search(r"total_solve_time\s+([\d.]+)", log)
        cuopt_time = float(mt.group(1)) if mt else wall
        return dict(injected=self._injector.injected,
                    objective=self._injector.objective,
                    inject_time=self._injector.inject_time,
                    wall_time=cuopt_time, log=log,
                    n_events=self._injector.n_events,
                    fetch_ok=self._injector.fetch_ok)


class _HttpSolveHandle:
    """HTTP cuOpt solve をバックグラウンドスレッドで走らせ、subprocess.Popen 互換の
    ``poll``/``terminate``/``wait``/``kill`` を提供するアダプタ。

    ``_ConcurrentInjector`` は ``proc.poll()`` が非Noneになったら ``sol_path`` を
    ``_parse_sol_file`` で読む。よってこのスレッドは、完了時に ``# Status:`` /
    ``# Objective value:`` ヘッダ付きの SCIP互換 .sol を ``sol_path`` へ書く。
    model へはスレッドから触らない(datamodel は起動前に main スレッドで構築済み)。
    """

    def __init__(self, datamodel: dict, server_url: str, time_limit: float,
                 sol_path: Path, log_path: Path, poll_interval: float):
        self._server_url = server_url
        self._sol_path = sol_path
        self._log_path = log_path
        self._time_limit = time_limit
        self._poll_interval = poll_interval
        self._datamodel = datamodel
        self._returncode: Optional[int] = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        base = self._server_url.rstrip("/")
        try:
            resp = _http_post_json(base + "/cuopt/request", self._datamodel,
                                   timeout=self._time_limit + 120)
            deadline = time.time() + self._time_limit + 120
            while isinstance(resp, dict) and len(resp) == 1 and "reqId" in resp:
                if time.time() > deadline:
                    break
                time.sleep(self._poll_interval)
                _, resp = _http_get_json(
                    base + "/cuopt/solution/" + str(resp["reqId"]),
                    timeout=self._time_limit + 120)
            if isinstance(resp, dict) and "response" in resp:
                sol = _extract_http_solution(resp)
                self._log_path.write_text(json.dumps(sol, default=str))
                if sol["vars"] and sol.get("status") in _FEASIBLE_STATUS:
                    _write_scip_sol(self._sol_path, sol)
            self._returncode = 0
        except (urllib.error.URLError, OSError, ValueError) as e:
            self._log_path.write_text(f"cuopt http error: {e}")
            self._returncode = 1

    def poll(self) -> Optional[int]:
        return None if self._thread.is_alive() else (self._returncode or 0)

    def terminate(self) -> None:  # HTTP はキャンセル不可。join に委ねる
        pass

    def wait(self, timeout: Optional[float] = None) -> None:
        self._thread.join(timeout)

    def kill(self) -> None:
        pass


def cuopt_concurrent(model: Model, time_limit: float = 15.0, *,
                     cuopt_cmd: Optional[list[str]] = None,
                     server_url: Optional[str] = None,
                     mps_dir: Optional[str] = None,
                     heuristics_only: bool = False,
                     first_feasible: bool = False,
                     num_cpu_threads: Optional[int] = None,
                     poll_interval: float = 1.0) -> CuoptConcurrent:
    """cuOpt(GPU)を非同期起動し、SCIP求解中に解を注入する常駐型ハイブリッドを仕込む。

    ``cuopt_warmstart`` の直列版(GPU完了を待ってから ``optimize``)と違い、cuOpt を
    サブプロセスで走らせたまま即座に返る。呼び出し後にそのまま ``model.optimize()``
    すると、SCIPの木探索と cuOpt のGPU探索が並走し、cuOpt が終了し次第その解が
    イベントハンドラ経由で ``trySol`` 注入される。GPU待ちの直列時間が消えるぶん
    wall-clock で有利(注入時点は ``result()`` の ``inject_time`` で確認できる)。

    Args:
        model: PySCIPOpt Model。最適化前のもの。この関数がイベントハンドラを登録する。
        time_limit: cuOpt 側の時間制限[秒]。SCIPの ``limits/time`` とは独立。
        cuopt_cmd: ``cuopt_warmstart`` と同じ。cuopt_cli 起動コマンドの prefix。
        server_url: cuOpt self-hosted サーバのベースURL(例 ``http://192.168.50.37:8000``)。
            指定すると並走はサブプロセスでなくHTTPスレッドで行う(GPU計算はサーバ側)。
            省略時は環境変数 ``MINLPKIT_CUOPT_URL`` を見る。解決されればHTTP経路。
        mps_dir: 一時MPS/.sol/ログの出力先。省略時は ``tempfile.mkdtemp()``。
        heuristics_only: cuOpt に ``--mip-heuristics-only true`` を渡す。
        first_feasible: True で ``--first-primal-feasible true``(最初の可行解で
            即終了)。注入レイテンシ最小化用。
        num_cpu_threads: cuOpt のCPU側B&Bスレッド数。並走時はSCIPとCPUを取り合うため
            小さめ(例: 論理コアの1/3)にするとSCIP側の速度低下を抑えられる。
        poll_interval: イベントハンドラが cuOpt 終了を確認する間隔[秒](SCIP求解時刻)。

    Returns:
        CuoptConcurrent: ``optimize()`` 後に ``result()`` を呼ぶハンドル。

    Note:
        SCIPのルートLPが ``time_limit`` より長い場合、NODESOLVED が発火せず注入が
        遅れる(ルートLP中の注入はできない)。cuOpt側が可行解ゼロの場合は何も
        注入されない(``result()["objective"]`` が None)。
    """
    url = _resolve_server_url(server_url)
    if url is not None:
        if not cuopt_available(server_url=url):
            raise RuntimeError(_http_hint(url, "GET /cuopt/health が200を返さない"))
        workdir = Path(mps_dir) if mps_dir is not None else Path(tempfile.mkdtemp())
        workdir.mkdir(parents=True, exist_ok=True)
        sol_path = workdir / "cuopt_concurrent.sol"
        log_path = workdir / "cuopt_concurrent.log"
        # datamodel は起動前に main スレッドで構築(以後 model へスレッドから触らない)
        datamodel = _model_to_datamodel(model, time_limit)
        model.writeProblem(str(workdir / "cuopt_concurrent.mps"))  # 成果物/デバッグ用
        t0 = time.perf_counter()
        handle = _HttpSolveHandle(datamodel, url, time_limit, sol_path, log_path,
                                  poll_interval)
        injector = _ConcurrentInjector(handle, sol_path, poll_interval, fetch_sol=None)
        model.includeEventhdlr(injector, "cuopt_concurrent",
                               "injects cuOpt solution during solve")
        return CuoptConcurrent(handle, injector, log_path, t0)

    cmd_prefix = list(cuopt_cmd) if cuopt_cmd is not None else list(_DEFAULT_CUOPT_CMD)
    is_wsl = bool(cmd_prefix) and cmd_prefix[0] == "wsl"
    if not cuopt_available(cmd_prefix):
        raise RuntimeError(_INSTALL_HINT)

    workdir = Path(mps_dir) if mps_dir is not None else Path(tempfile.mkdtemp())
    workdir.mkdir(parents=True, exist_ok=True)
    mps_path = workdir / "cuopt_concurrent.mps"
    sol_path = workdir / "cuopt_concurrent.sol"
    log_path = workdir / "cuopt_concurrent.log"

    model.writeProblem(str(mps_path))

    # WSL経由なら9pの遅さを避け、MPS読み・.sol書きともネイティブFS(/tmp)で行う
    mps_arg = _stage_mps_native(cmd_prefix, mps_path) if is_wsl else str(mps_path)
    sol_arg = (f"/tmp/minlpkit_{os.getpid()}_{sol_path.name}" if is_wsl
               else str(sol_path))

    cmd = cmd_prefix + ["--time-limit", str(time_limit), "--solution-file", sol_arg]
    if heuristics_only:
        cmd += ["--mip-heuristics-only", "true"]
    if first_feasible:
        cmd += ["--first-primal-feasible", "true"]
    if num_cpu_threads is not None:
        cmd += ["--num-cpu-threads", str(num_cpu_threads)]
    cmd.append(mps_arg)

    # stdoutはファイルへ(PIPEだとバッファ詰まりでcuOptが止まりうる)
    t0 = time.perf_counter()
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(cmd, stdout=log_f, stderr=subprocess.STDOUT)

    fetch = (lambda: _fetch_from_wsl(cmd_prefix, sol_arg, sol_path)) if is_wsl else None
    injector = _ConcurrentInjector(proc, sol_path, poll_interval, fetch_sol=fetch)
    model.includeEventhdlr(injector, "cuopt_concurrent",
                           "injects cuOpt solution during solve")
    return CuoptConcurrent(proc, injector, log_path, t0)
