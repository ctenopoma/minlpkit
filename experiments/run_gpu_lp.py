"""cuPDLP検証: cuOptのLP解法(GPU一次法 PDLP / GPU barrier / CPU dual simplex)比較

Phase 11で「集合分割largeはcuOptのルートLP(dual simplex)が退化で停滞し
GPUヒューリスティクス未到達」という負の結果が出た。LP側をGPU一次法(PDLP=cuPDLP系)や
GPU barrierに切り替えると解消するかを実測する。

  A) LP緩和(--relaxation)を --method 1(PDLP)/ 2(dual simplex)/ 3(barrier)で解き比べ
  B) MIP本体を --method 指定で解き、ルートLP律速の不発が解消するか確認

前提: results/gpu/<tag>.mps が生成済み(run_gpu_heuristic.py が書き出す)。
実行: uv run python experiments/run_gpu_lp.py --tag setpart_large --time 120
出力: コンソール比較表 + results/gpu/lp_<tag>_<mode>_<method>.log
"""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "results" / "gpu"
CUOPT_CLI = "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"
WSL_DISTRO = "Ubuntu"

METHODS = {1: "PDLP(GPU)", 2: "DualSimplex(CPU)", 3: "Barrier(GPU)"}


def to_wsl_path(p: Path) -> str:
    s = str(p.resolve())
    return f"/mnt/{s[0].lower()}{s[2:].replace(chr(92), '/')}"


def run(mps: Path, method: int, time_limit: float, relaxation: bool, log_path: Path) -> dict:
    cmd = ["wsl", "-d", WSL_DISTRO, "--", CUOPT_CLI,
           "--time-limit", str(time_limit), "--method", str(method)]
    if relaxation:
        cmd.append("--relaxation")
    cmd.append(to_wsl_path(mps))
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 180)
    wall = time.perf_counter() - t0
    log = proc.stdout + proc.stderr
    log_path.write_text(log, encoding="utf-8", errors="replace")

    # LP: "Objective <val>" 等 / MIP: "Solution objective: <val> ..." をゆるくparse
    obj = status = None
    ms = re.search(r"Solution objective:\s*([-\d.eE+]+)", log)
    if ms:
        obj = float(ms.group(1))
    else:
        mo = re.search(r"[Oo]bjective(?:\s+value)?[:\s=]+([-\d.eE+]+)", log)
        if mo:
            obj = float(mo.group(1))
    for kw in ("Optimal", "TimeLimit", "Time limit", "Infeasible", "FeasibleFound"):
        if kw in log:
            status = kw
            break
    return dict(method=METHODS[method], wall=wall, objective=obj, status=status,
                rc=proc.returncode, log_tail=log.strip().splitlines()[-3:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="setpart_large")
    ap.add_argument("--time", type=float, default=120.0)
    ap.add_argument("--modes", default="lp,mip", help="lp=--relaxation比較 / mip=MIP本体比較")
    args = ap.parse_args()

    mps = OUTDIR / f"{args.tag}.mps"
    if not mps.exists():
        raise SystemExit(f"{mps} が無い。先に run_gpu_heuristic.py で生成すること")

    for mode in args.modes.split(","):
        relax = mode == "lp"
        print(f"\n=== {args.tag} {'LP緩和' if relax else 'MIP本体'} "
              f"(--time-limit {args.time}s) ===")
        print(f"{'method':18} {'wall(s)':>8} {'objective':>14} {'status':>12}")
        for method in METHODS:
            log_path = OUTDIR / f"lp_{args.tag}_{mode}_{method}.log"
            r = run(mps, method, args.time, relax, log_path)
            obj_s = f"{r['objective']:,.2f}" if r["objective"] is not None else "-"
            print(f"{r['method']:18} {r['wall']:8.1f} {obj_s:>14} {str(r['status']):>12}"
                  + ("" if r["rc"] == 0 else f"  [rc={r['rc']}]"))


if __name__ == "__main__":
    main()
