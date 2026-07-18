"""サンプルモデルをモニタ付きで求解し、ログCSVとダッシュボードHTMLを出力する。

実行例:
  uv run python experiments/run_monitor.py --model plant --time 120
  uv run python experiments/run_monitor.py --model uc --time 60
モデル: uc / sched / plant
出力: results/<model>_log.csv, results/<model>_dashboard.html
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from viz.monitor import primal_gap_series, solve_with_monitor
from viz.plots import build_dashboard
from viz.run_logger import RunLogger, new_run_id

MODELS = {
    "uc": ("unit_commitment", "プラント系 Unit Commitment"),
    "sched": ("scheduling", "バッチスケジューリング"),
    "plant": ("scheduling_plant", "バッチ反応器スケジューリング(プラント物理入り)"),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    ap.add_argument("--time", type=float, default=120.0)
    ap.add_argument("--gap", type=float, default=0.01)
    args = ap.parse_args()

    module_name, title = MODELS[args.model]
    module = __import__(module_name)
    model = module.build_model()
    model.hideOutput()

    # 書き手側の run ロガー(server.py がこれを tail してライブ配信する)
    run_id = new_run_id(args.model)
    logger = RunLogger(run_id, meta=dict(
        model=args.model, title=title,
        params=dict(time_limit=args.time, gap_limit=args.gap)))

    print(f"solving {module_name} (time_limit={args.time}s, gap_limit={args.gap * 100}%) ...")
    print(f"run_id={run_id}  (ライブ表示: 別ターミナルで `uv run python -m viz.server`)")
    mon, summary = solve_with_monitor(model, time_limit=args.time, gap_limit=args.gap, logger=logger)
    df = mon.to_frame()
    pg = primal_gap_series(df, summary["primal"])

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    csv_path = outdir / f"{args.model}_log.csv"
    html_path = outdir / f"{args.model}_dashboard.html"
    df.to_csv(csv_path, index=False)
    build_dashboard(df, pg, summary, title, str(html_path))

    print(f"status={summary['status']}  obj={summary['objective']}  "
          f"gap={summary['gap'] * 100 if summary['gap'] is not None else float('nan'):.2f}%  "
          f"nodes={summary['nodes']:,}  sols={summary['nsols']}")
    print(f"log rows={len(df)} -> {csv_path}")
    print(f"dashboard -> {html_path}")


if __name__ == "__main__":
    main()
