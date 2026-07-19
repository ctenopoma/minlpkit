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

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from pyscipopt import SCIP_EVENTTYPE, Eventhdlr, Model

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
    "詳細は docs/manual.md 7節(GPU warm start)。導入確認は mk.cuopt_available()。")

_availability_cache: dict[tuple, bool] = {}


def cuopt_available(cuopt_cmd: Optional[list[str]] = None) -> bool:
    """cuOpt CLI が実行可能か(WSL2/GPU環境が使えるか)を返す。

    minlpkit のGPU機能は完全に任意で、追加のPython依存も持たない(cuOpt本体は
    WSL2側の別venv)。未導入環境でも import・診断は通常どおり動くので、
    ``cuopt_warmstart``/``cuopt_concurrent`` を呼ぶ前の分岐にこの関数を使う。
    結果はプロセス内でキャッシュされる。

    Args:
        cuopt_cmd: ``cuopt_warmstart`` と同じコマンド prefix。既定はWSL2経由。

    Returns:
        bool: cuopt_cli が起動可能なら True。
    """
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


def cuopt_warmstart(model: Model, time_limit: float = 15.0, *,
                    cuopt_cmd: Optional[list[str]] = None,
                    mps_dir: Optional[str] = None,
                    heuristics_only: bool = False,
                    num_cpu_threads: Optional[int] = None) -> dict:
    """cuOpt(GPU)で短時間探索し、見つかった可行解を model に warm start として注入する。

    ``model`` を MPS に書き出して WSL2 上の cuOpt CLI に渡し、標準出力ログから目的値・
    下界・ギャップを読み取る。可行解が得られていれば ``.sol`` を ``readSolFile`` +
    ``addSol`` で ``model`` に注入する。呼び出しは ``model.optimize()`` より前に行うこと
    (最適化中/後のモデルへ注入しても意味がない)。

    Args:
        model: PySCIPOpt Model。最適化前のもの(``writeProblem`` できる状態)。
        time_limit: cuOpt CLI に渡す時間制限[秒]。サブプロセスのタイムアウトは
            ``time_limit + 120`` 秒(cuOptの起動・GPU初期化のオーバーヘッド分の余裕)。
        cuopt_cmd: cuopt_cli を起動するコマンド prefix のリスト。既定は
            ``["wsl", "-d", "Ubuntu", "--", "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]``。
            prefix の先頭が ``"wsl"`` でなければネイティブ実行とみなし、パスは
            Windows→WSL変換をせずそのまま渡す(例: Linux上で ``["cuopt_cli"]``)。
        mps_dir: 一時MPSファイルの出力先ディレクトリ。省略時は ``tempfile.mkdtemp()``。
            WSL側から見える(=Windowsの通常ドライブ上の)ディレクトリである必要がある。
        heuristics_only: True で cuOpt に ``--mip-heuristics-only true`` を渡す
            (LP緩和による下界証明を省き、ヒューリスティクスだけで可行解探索に専念させる)。
        num_cpu_threads: cuOpt のCPU側B&Bスレッド数(``--num-cpu-threads``)。
            省略時はcuOpt既定(全論理コア)。

    Returns:
        dict: ``objective``(cuOptが見つけた目的値。可行解無しなら None)、
        ``bound``(cuOptの下界)、``gap``(相対ギャップ)、
        ``accepted``(``model.addSol`` が受理したか。可行解が無ければ False)、
        ``wall_time``(cuOpt呼び出しの実測秒数)、``log``(cuOpt標準出力全文)。

    Raises:
        RuntimeError: cuopt_cli がゼロ以外の終了コードを返した場合(末尾ログ付き)。

    Note:
        cuOptは最適性証明をしない(下界はヒューリスティックな推定に留まる)ため、
        本関数の役割は「可行解の種をSCIPに渡す」ことに限る。証明はSCIPの通常の
        ``optimize()`` に委ねる想定(cuOpt=可行解探索、SCIP=証明、の分業)。
        参考実装: ``experiments/run_gpu_heuristic.py``。
    """
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


def cuopt_concurrent(model: Model, time_limit: float = 15.0, *,
                     cuopt_cmd: Optional[list[str]] = None,
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
