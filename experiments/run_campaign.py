"""campaign 実行CLI: ablation(制約On/Off犯人探し)/ scenario(入力切替)

「最適化が収束しない/実行不可能 → 制約を1個ずつOn/Offして犯人を探す」
「入力シナリオを切り替えて一括求解する」という手作業を campaign として自動化する。
各メンバーは通常の run として results/runs/ に記録され、campaign 全体の要約と
提案(verdicts)は results/campaigns/<id>/campaign.json に出る。

実行例:
  uv run python experiments/run_campaign.py --kind ablate --time 15
  uv run python experiments/run_campaign.py --kind scenario --time 15
  uv run python experiments/run_campaign.py --kind ablate --otel http://localhost:4318

閲覧: uv run python -m minlpkit.live.server → http://127.0.0.1:5000/campaigns
      (--otel 指定時は Grafana http://localhost:3000 でも閲覧可。ops/README.md 参照)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))  # samples パッケージをルートから import

from minlpkit.live import ablate, scenario_sweep  # noqa: E402

import samples.others.scheduling_plant as sp  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=["ablate", "scenario"], default="ablate")
    ap.add_argument("--time", type=float, default=15.0, help="各メンバーの制限時間[秒]")
    ap.add_argument("--otel", default=None, metavar="ENDPOINT",
                    help="OTLPエンドポイント(例 http://localhost:4318)。指定で完了時にOTelエクスポート")
    args = ap.parse_args()

    if args.kind == "ablate":
        # 物理制約のグループを1つずつOffにして「どれが収束を重くしているか」を観測する。
        # 需要充足(三重積)・除熱(三重積)・反応速度論(exp)が非線形の主犯候補。
        groups = {
            "demand": "demand_",        # 需要充足 n·s·X ≥ d(三重積)
            "cooling": "cooling_",      # 除熱能力(三重積)
            "kinetics": lambda name: name.startswith(("arrhenius_", "conversion_")),
            "energy": "energy_",        # エネルギー収支(三重積、目的に効く)
            "load": "load_",            # マシン負荷(makespan結合)
        }
        df = ablate(sp.build_model, groups, name="plant", time_limit=args.time,
                    otel_endpoint=args.otel)
    else:
        # 需要シナリオを切替。1.5倍までは可行(難例)、2.0倍以上は実行不可能になる
        scales = {"low_0.6": 0.6, "base_1.0": 1.0, "high_1.5": 1.5,
                  "tight_2.0": 2.0, "over_capacity_3.0": 3.0}
        df = scenario_sweep(lambda sc: sp.build_model(demand_scale=sc), scales,
                            name="plant", time_limit=args.time, otel_endpoint=args.otel)

    print()
    print(df.to_string(index=False))
    print("\n閲覧: uv run python -m minlpkit.live.server → http://127.0.0.1:5000/campaigns")


if __name__ == "__main__":
    main()
