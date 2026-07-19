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

import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from pyscipopt import Model

_DEFAULT_CUOPT_CMD = ["wsl", "-d", "Ubuntu", "--",
                       "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]

# cuOptログの最終サマリ行: "Solution objective: <obj> , relative_mip_gap <gap> solution_bound <bound>"
_SUMMARY = re.compile(
    r"Solution objective:\s*([-\d.eE+]+)\s*,\s*relative_mip_gap\s*([-\d.eE+]+)"
    r"\s*solution_bound\s*([-\d.eE+]+)")


def _to_wsl_path(p: Path) -> str:
    """Windows パス ``D:\\foo\\bar`` を WSL パス ``/mnt/d/foo/bar`` へ変換する。"""
    s = str(p.resolve())
    drive, rest = s[0].lower(), s[2:].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


def cuopt_warmstart(model: Model, time_limit: float = 15.0, *,
                    cuopt_cmd: Optional[list[str]] = None,
                    mps_dir: Optional[str] = None,
                    heuristics_only: bool = False) -> dict:
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

    workdir = Path(mps_dir) if mps_dir is not None else Path(tempfile.mkdtemp())
    workdir.mkdir(parents=True, exist_ok=True)
    mps_path = workdir / "cuopt_warmstart.mps"
    sol_path = workdir / "cuopt_warmstart.sol"

    model.writeProblem(str(mps_path))

    mps_arg = _to_wsl_path(mps_path) if is_wsl else str(mps_path)
    sol_arg = _to_wsl_path(sol_path) if is_wsl else str(sol_path)

    cmd = cmd_prefix + ["--time-limit", str(time_limit), "--solution-file", sol_arg]
    if heuristics_only:
        cmd += ["--mip-heuristics-only", "true"]
    cmd.append(mps_arg)

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 120)
    wall = time.perf_counter() - t0
    log = proc.stdout
    if proc.returncode != 0:
        raise RuntimeError(
            f"cuopt_cli failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}\n{log[-2000:]}")

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
