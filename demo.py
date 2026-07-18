"""minlpkit 一気通貫デモ (Phase 5)

可視化→診断→改善→再検証 を1本で通す:
  1. analyze(plant baseline) で観測量収集 + 診断 → レポートHTML
  2. 診断の推薦(n·s厳密線形化)を適用
  3. compare_variants で baseline vs 改善 を before/after 比較

実行: uv run python demo.py
出力: results/report_plant.html, コンソールに診断と改善効果
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "samples"))

import minlpkit as mk
import scheduling_plant as sp
from viz.plant_terms import evaluate_terms


def main() -> None:
    print("=" * 60)
    print("1. analyze: 観測量収集 + 診断")
    print("=" * 60)
    report = mk.analyze(lambda: sp.build_model(), name="plant(baseline)",
                        time_limit=15, interval_terms_fn=evaluate_terms)
    print(report.summary())
    report.dashboard("results/report_plant.html")
    print("-> results/report_plant.html")

    print("\n" + "=" * 60)
    print("2-3. 推薦(n·s厳密線形化)を適用し before/after 比較")
    print("=" * 60)
    df = mk.compare_variants({
        "baseline(n·s双線形)": lambda: sp.build_model(linearize_ns=False),
        "改善(n·s厳密線形化)": lambda: sp.build_model(linearize_ns=True),
    }, time_limit=15)
    print(df[["variant", "root_dual", "final_dual", "final_gap", "nodes"]].to_string(index=False))

    base = df.iloc[0]
    imp = df.iloc[1]
    root_gain = (imp["root_dual"] - base["root_dual"]) / base["root_dual"] * 100
    print(f"\n結論: 推薦した厳密線形化で ルート双対境界 {base['root_dual']:.0f}→{imp['root_dual']:.0f} "
          f"(+{root_gain:.0f}%)、gap {base['final_gap']*100:.0f}%→{imp['final_gap']*100:.0f}%")
    print("可視化→診断→改善→再検証 の一気通貫が minlpkit で完了。")


if __name__ == "__main__":
    main()
