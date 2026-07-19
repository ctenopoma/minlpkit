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

from minlpkit.gpu import cuopt_concurrent, cuopt_warmstart
from minlpkit.live import RunLogger, new_run_id, solve_with_monitor

ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "results" / "gpu"
CUOPT_CLI = "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"
WSL_DISTRO = "Ubuntu"

MODELS = {
    "gap": ("samples.packing_and_cutting.gap_large", "大規模一般化割当 (GAP)"),
    "setpart": ("samples.graph_and_discrete.set_partitioning", "大規模集合分割"),
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


def _result_from_monitor(mon, summary: dict) -> dict:
    """`solve_with_monitor` の (SolveMonitor, summary) からIncumbentTracker互換の
    結果dict(ttff/best/dual/gap/nsols/time/trajectory)を組み立てる。

    `--live` 時は SolveMonitor 自体が logger へイベントを逐次書き込み済みなので、
    ここでは軌跡(incumbentイベントのみ抽出した (time, primal) のリスト)を
    再構成するだけでよい(IncumbentTrackerとの二重計装を避ける)。
    """
    df = mon.to_frame()
    inc = df[df["event"] == "incumbent"] if not df.empty else df
    traj = list(zip(inc["time"], inc["primal"])) if not inc.empty else []
    return dict(
        ttff=traj[0][0] if traj else None,
        best=summary["primal"],
        dual=summary["dual"],
        gap=summary["gap"],
        nsols=summary["nsols"],
        time=summary["time"],
        trajectory=traj,
    )


def run_scip(model_key: str, scale: str, time_limit: float, logger: RunLogger | None = None) -> dict:
    m = build(model_key, scale)
    m.hideOutput()
    if logger is not None:
        # solve_with_monitor自体がSolveMonitorイベントハンドラでlogger.appendするため、
        # IncumbentTrackerによる二重計装はしない
        mon, summary = solve_with_monitor(m, time_limit=time_limit, logger=logger)
        return _result_from_monitor(mon, summary)
    tracker = IncumbentTracker()
    m.includeEventhdlr(tracker, "inc_track", "incumbent trajectory")
    m.setParam("limits/time", time_limit)
    m.optimize()
    traj = tracker.trajectory
    return dict(
        ttff=traj[0][0] if traj else None,
        best=m.getPrimalbound() if m.getNSols() else None,
        dual=m.getDualbound(),
        gap=m.getGap() if m.getNSols() else None,
        nsols=m.getNSols(),
        time=m.getSolvingTime(),
        trajectory=traj,
    )


def run_hybrid(model_key: str, scale: str, gpu_budget: float, time_limit: float,
               logger: RunLogger | None = None) -> dict:
    """cuOptを短時間走らせてwarm start注入した後、SCIPで続行する(minlpkit.gpu経由)。"""
    m = build(model_key, scale)
    cmd = ["wsl", "-d", WSL_DISTRO, "--", CUOPT_CLI]
    pre = cuopt_warmstart(m, time_limit=gpu_budget, cuopt_cmd=cmd, mps_dir=str(OUTDIR))
    m.hideOutput()
    if logger is not None:
        # 注入解(t=0)はSCIP側のイベントハンドラより前に addSol 済みなのでBESTSOLFOUNDに
        # 乗らない。solve_with_monitor呼び出し前に明示的に1件書いておく
        if pre["accepted"]:
            logger.append(dict(time=0.0, nodes=0, primal=pre["objective"], dual=None,
                                gap=None, event="incumbent", nsols=1))
        mon, summary = solve_with_monitor(m, time_limit=time_limit, logger=logger)
        result = _result_from_monitor(mon, summary)
        if pre["accepted"]:
            result["trajectory"] = [(0.0, pre["objective"])] + result["trajectory"]
            result["ttff"] = 0.0
        result.update(injected=pre["accepted"], cuopt_obj=pre["objective"], cuopt_time=pre["wall_time"])
        return result
    tracker = IncumbentTracker()
    m.includeEventhdlr(tracker, "inc_track", "incumbent trajectory")
    m.setParam("limits/time", time_limit)
    m.optimize()
    # 注入解はBESTSOLFOUNDイベントに乗らないため、軌跡の先頭に明示的に置く
    # (時刻はSCIP求解開始時点=0。GPU先行時間は cuopt_time として別掲)
    traj = tracker.trajectory
    if pre["accepted"]:
        traj = [(0.0, pre["objective"])] + traj
    return dict(
        ttff=traj[0][0] if traj else None,
        best=m.getPrimalbound() if m.getNSols() else None,
        dual=m.getDualbound(),
        gap=m.getGap() if m.getNSols() else None,
        nsols=m.getNSols(),
        time=m.getSolvingTime(),
        trajectory=traj,
        injected=pre["accepted"],
        cuopt_obj=pre["objective"],
        cuopt_time=pre["wall_time"],
    )


def run_concurrent(model_key: str, scale: str, gpu_budget: float, time_limit: float,
                   logger: RunLogger | None = None) -> dict:
    """常駐型: cuOptをSCIPと並走させ、終了し次第mid-solveで解を注入する(GPU待ちゼロ)。

    注入解は trySol 経由で incumbent になるため BESTSOLFOUND が発火し、
    IncumbentTracker / SolveMonitor の軌跡に自動で乗る(hybridのような手動追記は不要)。
    """
    m = build(model_key, scale)
    m.hideOutput()
    cmd = ["wsl", "-d", WSL_DISTRO, "--", CUOPT_CLI]
    # 並走中のCPU競合を抑える(cuOptのCPU B&Bを8スレッドに制限。GPUヒューリスティクスは無関係)
    h = cuopt_concurrent(m, time_limit=gpu_budget, cuopt_cmd=cmd, mps_dir=str(OUTDIR),
                         num_cpu_threads=8)
    if logger is not None:
        mon, summary = solve_with_monitor(m, time_limit=time_limit, logger=logger)
        result = _result_from_monitor(mon, summary)
    else:
        tracker = IncumbentTracker()
        m.includeEventhdlr(tracker, "inc_track", "incumbent trajectory")
        m.setParam("limits/time", time_limit)
        m.optimize()
        traj = tracker.trajectory
        result = dict(
            ttff=traj[0][0] if traj else None,
            best=m.getPrimalbound() if m.getNSols() else None,
            dual=m.getDualbound(),
            gap=m.getGap() if m.getNSols() else None,
            nsols=m.getNSols(),
            time=m.getSolvingTime(),
            trajectory=traj,
        )
    info = h.result()
    result.update(injected=info["injected"], cuopt_obj=info["objective"],
                  cuopt_time=info["wall_time"], inject_time=info["inject_time"])
    return result


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


def _make_live_logger(args, arm: str, title: str) -> RunLogger:
    """アーム1本を1runとして`results/runs/`に記録する`RunLogger`を作る。

    meta の model/scale/arm/params は比較モードの「設定の差分」テーブルで
    アーム間の違いが見えるように、既存run(sweep等)と同じ形(model/title/params)に
    合わせつつ arm/scale をトップレベルにも残す。
    """
    run_id = new_run_id(f"gpu_{args.model}_{args.scale}_{arm}")
    params = dict(time_limit=args.time)
    if arm in ("hybrid", "concurrent"):
        params["gpu_budget"] = args.gpu_budget
    return RunLogger(run_id, meta=dict(
        model=f"gpu_{args.model}", title=f"{title} ({args.scale}) [{arm}]",
        arm=arm, scale=args.scale, params=params))


def _log_cuopt_run(logger: RunLogger, result: dict) -> None:
    """cuOptアームの軌跡(実行後にまとめて得たもの)を1runとしてRunLoggerへ書く。

    cuOptは時刻ごとのdual boundを個別に出さない(ログの最終サマリ行にのみ
    最終dual boundが出る)ため、各イベントのdualはNoneとし、最後のイベントにだけ
    最終dual/gapを併記する(仕様上は「無ければ省略」だが、ここでは値があるので載せる)。
    """
    traj = result["trajectory"]
    n = len(traj)
    for i, (t, obj) in enumerate(traj):
        is_last = i == n - 1
        logger.append(dict(
            time=t, nodes=None, primal=obj,
            dual=result["dual"] if is_last else None,
            gap=result["gap"] if is_last else None,
            event="incumbent", nsols=i + 1,
        ))
    logger.finish(dict(
        status="completed", objective=result["best"], primal=result["best"],
        dual=result["dual"], gap=result["gap"], nodes=None,
        time=result["time"], nsols=result["nsols"],
    ))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="gap")
    ap.add_argument("--scale", default="large")
    ap.add_argument("--time", type=float, default=60.0, help="各アームの求解時間")
    ap.add_argument("--gpu-budget", type=float, default=15.0, help="hybridでのcuOpt先行時間")
    ap.add_argument("--arms", default="scip,cuopt,hybrid,concurrent")
    ap.add_argument("--live", action="store_true",
                     help="各アームをresults/runs/にrunとして記録し、ライブUIの比較モードで見られるようにする")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    tag = f"{args.model}_{args.scale}"
    title = MODELS[args.model][1]
    arms = args.arms.split(",")
    results: dict[str, dict] = {}

    # MPS出力(cuoptアーム用。hybridはminlpkit.gpu.cuopt_warmstart内部で自前に書き出す)
    mps = OUTDIR / f"{tag}.mps"
    if "cuopt" in arms:
        m = build(args.model, args.scale)
        m.hideOutput()
        m.writeProblem(str(mps))
        print(f"[prep] MPS書き出し: {mps.name} (vars={m.getNVars()}, conss={m.getNConss()})")

    if "scip" in arms:
        print(f"[scip] 純SCIP {args.time}s ...")
        logger = _make_live_logger(args, "scip", title) if args.live else None
        results["scip"] = run_scip(args.model, args.scale, args.time, logger=logger)
        if logger is not None:
            print(f"         run_id={logger.run_id}")

    if "cuopt" in arms:
        print(f"[cuopt] cuOpt(GPU) {args.time}s ...")
        results["cuopt"] = run_cuopt(mps, OUTDIR / f"{tag}_cuopt.sol", args.time)
        if args.live:
            logger = _make_live_logger(args, "cuopt", title)
            _log_cuopt_run(logger, results["cuopt"])
            print(f"         run_id={logger.run_id}")

    if "hybrid" in arms:
        print(f"[hybrid] cuOpt {args.gpu_budget}s → SCIP {args.time}s (minlpkit.gpu.cuopt_warmstart) ...")
        logger = _make_live_logger(args, "hybrid", title) if args.live else None
        results["hybrid"] = run_hybrid(args.model, args.scale, args.gpu_budget, args.time, logger=logger)
        if logger is not None:
            print(f"         run_id={logger.run_id}")

    if "concurrent" in arms:
        print(f"[concurrent] cuOpt {args.gpu_budget}s ∥ SCIP {args.time}s (minlpkit.gpu.cuopt_concurrent) ...")
        logger = _make_live_logger(args, "concurrent", title) if args.live else None
        results["concurrent"] = run_concurrent(args.model, args.scale, args.gpu_budget,
                                               args.time, logger=logger)
        if logger is not None:
            print(f"         run_id={logger.run_id}")

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
        if arm == "concurrent":
            obj_s = f"{r['cuopt_obj']:,.0f}" if r.get("cuopt_obj") is not None else "なし"
            it = f"{r['inject_time']:.1f}s時点" if r.get("inject_time") is not None else "注入なし"
            print(f"         (並走cuOpt解 {obj_s}: {it}, "
                  f"{'受理' if r.get('injected') else '不受理'}, GPU実測 {r['cuopt_time']:.1f}s)")
        for t, obj in r["trajectory"]:
            rows.append(dict(arm=arm, time=t, objective=obj))

    import pandas as pd
    csv_path = OUTDIR / f"{tag}_compare.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    print(f"\nincumbent軌跡: {csv_path}")


if __name__ == "__main__":
    main()
