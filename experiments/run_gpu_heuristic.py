"""GPU primal heuristics (cuOpt) × SCIP のハイブリッド実験

3アーム比較で「GPUは可行解探索、CPUは証明」という分業(cuOptノートの構成)を検証する:

  scip   : 純SCIP(ベースライン)。incumbent軌跡とTTFFを記録
  cuopt  : cuOpt単体(WSL2のGPUで実行)。ログからincumbent軌跡を抽出
  hybrid : cuOptを短時間走らせ、得た解をSCIPにwarm start注入して続行

前提: WSL2 Ubuntu に cuopt-cu13 導入済み(~/cuopt-env)。GPUはWSLから見えること。

実行例:
  uv run python experiments/run_gpu_heuristic.py --model gap --scale large --time 60
  uv run python experiments/run_gpu_heuristic.py --model setpart --scale large --time 60
出力: results/gpu/<model>_<scale>_compare.csv とコンソール比較表
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyscipopt import SCIP_EVENTTYPE, Eventhdlr, Model

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "results" / "gpu"
CUOPT_CLI = "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"
WSL_DISTRO = "Ubuntu"

MODELS = {
    "gap": ("samples.gap_large", "大規模一般化割当 (GAP)"),
    "setpart": ("samples.set_partitioning", "大規模集合分割"),
}


def to_wsl_path(p: Path) -> str:
    s = str(p.resolve())
    drive, rest = s[0].lower(), s[2:].replace("\\", "/")
    return f"/mnt/{drive}{rest}"


class IncumbentTracker(Eventhdlr):
    """BESTSOLFOUND ごとに (経過秒, 目的値) を記録する。"""

    def __init__(self):
        self.trajectory: list[tuple[float, float]] = []

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.BESTSOLFOUND, self)

    def eventexec(self, event):
        self.trajectory.append(
            (self.model.getSolvingTime(), self.model.getPrimalbound()))


def build(model_key: str, scale: str) -> Model:
    module = __import__(MODELS[model_key][0], fromlist=["build_model"])
    return module.build_model(scale)


def run_scip(model_key: str, scale: str, time_limit: float,
             warmstart_sol: Path | None = None) -> dict:
    m = build(model_key, scale)
    tracker = IncumbentTracker()
    m.includeEventhdlr(tracker, "inc_track", "incumbent trajectory")
    m.setParam("limits/time", time_limit)
    m.hideOutput()
    injected = False
    if warmstart_sol is not None:
        sol = m.readSolFile(str(warmstart_sol))
        injected = m.addSol(sol)
    m.optimize()
    traj = tracker.trajectory
    return dict(
        ttff=traj[0][0] if traj else None,
        best=m.getPrimalbound() if m.getNSols() else None,
        dual=m.getDualbound(),
        gap=m.getGap() if m.getNSols() else None,
        nsols=m.getNSols(),
        time=m.getSolvingTime(),
        injected=injected,
        trajectory=traj,
    )


# cuOptログのincumbent行:  D/B行(表形式)・H行・"New solution from primal heuristics"
_ROW = re.compile(r"^[DBH*]?\s.*?([+-]\d\.\d+e[+-]\d+).*?(\d+\.\d+)\s*$")
_HEUR = re.compile(r"New solution from primal heuristics\. Objective ([+-]\d\.\d+e[+-]\d+)\. Time (\d+\.\d+)")


def run_cuopt(mps: Path, sol_out: Path, time_limit: float,
              heuristics_only: bool = False) -> dict:
    cmd = ["wsl", "-d", WSL_DISTRO, "--", CUOPT_CLI,
           "--time-limit", str(time_limit),
           "--solution-file", to_wsl_path(sol_out)]
    if heuristics_only:
        cmd += ["--mip-heuristics-only", "true"]
    cmd.append(to_wsl_path(mps))
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=time_limit + 120)
    wall = time.perf_counter() - t0
    log = proc.stdout
    if proc.returncode != 0:
        raise RuntimeError(f"cuopt_cli failed (rc={proc.returncode}):\n{proc.stderr[-2000:]}\n{log[-2000:]}")

    traj: list[tuple[float, float]] = []
    for line in log.splitlines():
        mh = _HEUR.search(line)
        if mh:
            traj.append((float(mh.group(2)), float(mh.group(1))))
            continue
        if line[:1] in ("D", "B", "H") and "e+" in line:
            mr = _ROW.match(line)
            if mr:
                traj.append((float(mr.group(2)), float(mr.group(1))))

    best = bound = None
    ms = re.search(r"Solution objective: ([-\d.eE+]+)\s*, relative_mip_gap ([-\d.eE+]+) solution_bound ([-\d.eE+]+)", log)
    gap = None
    if ms:
        best, gap, bound = float(ms.group(1)), float(ms.group(2)), float(ms.group(3))
    return dict(
        ttff=traj[0][0] if traj else None,
        best=best, dual=bound, gap=gap,
        nsols=len(traj), time=wall, trajectory=traj, log=log,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="gap")
    ap.add_argument("--scale", default="large")
    ap.add_argument("--time", type=float, default=60.0, help="各アームの求解時間")
    ap.add_argument("--gpu-budget", type=float, default=15.0, help="hybridでのcuOpt先行時間")
    ap.add_argument("--arms", default="scip,cuopt,hybrid")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}_{args.scale}"
    title = MODELS[args.model][1]
    arms = args.arms.split(",")
    results: dict[str, dict] = {}

    # MPS出力(cuopt/hybrid共用)
    mps = OUTDIR / f"{tag}.mps"
    if any(a in arms for a in ("cuopt", "hybrid")):
        m = build(args.model, args.scale)
        m.hideOutput()
        m.writeProblem(str(mps))
        print(f"[prep] MPS書き出し: {mps.name} (vars={m.getNVars()}, conss={m.getNConss()})")

    if "scip" in arms:
        print(f"[scip] 純SCIP {args.time}s ...")
        results["scip"] = run_scip(args.model, args.scale, args.time)

    if "cuopt" in arms:
        print(f"[cuopt] cuOpt(GPU) {args.time}s ...")
        results["cuopt"] = run_cuopt(mps, OUTDIR / f"{tag}_cuopt.sol", args.time)

    if "hybrid" in arms:
        print(f"[hybrid] cuOpt {args.gpu_budget}s → SCIP {args.time}s ...")
        sol_path = OUTDIR / f"{tag}_warm.sol"
        pre = run_cuopt(mps, sol_path, args.gpu_budget)
        # cuOptが可行解を出せなかった場合はゼロ埋め.solなので注入しない
        warm = sol_path if pre["best"] is not None else None
        res = run_scip(args.model, args.scale, args.time, warmstart_sol=warm)
        res["cuopt_obj"] = pre["best"]
        res["cuopt_time"] = pre["time"]
        results["hybrid"] = res

    # 比較表
    print(f"\n=== {title} ({args.scale}) 各アーム {args.time}s ===")
    hdr = f"{'arm':8} {'TTFF(s)':>8} {'best':>12} {'dual':>12} {'gap%':>7} {'sols':>5}"
    print(hdr + "\n" + "-" * len(hdr))
    rows = []
    for arm, r in results.items():
        gap_pct = r["gap"] * 100 if r.get("gap") is not None else float("nan")
        print(f"{arm:8} {r['ttff'] if r['ttff'] is not None else float('nan'):8.2f} "
              f"{r['best'] if r['best'] is not None else float('nan'):12,.0f} "
              f"{r['dual'] if r['dual'] is not None else float('nan'):12,.0f} "
              f"{gap_pct:7.2f} {r['nsols']:5}")
        if arm == "hybrid":
            obj_s = f"{r['cuopt_obj']:,.0f}" if r.get("cuopt_obj") is not None else "なし"
            print(f"         (cuOpt解 {obj_s} を注入: "
                  f"{'受理' if r.get('injected') else '不受理'}, GPU先行 {r['cuopt_time']:.1f}s)")
        for t, obj in r["trajectory"]:
            rows.append(dict(arm=arm, time=t, objective=obj))

    import pandas as pd
    csv_path = OUTDIR / f"{tag}_compare.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f"\nincumbent軌跡: {csv_path}")


if __name__ == "__main__":
    main()
