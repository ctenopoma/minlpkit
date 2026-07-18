"""Phase 4: 被約コスト固定の効果検証(SCIP内蔵 redcost 伝播器)

被約コスト固定はSCIPが redcost 伝播器(既定ON)で自動実施する。手動再実装は冗長なので、
内蔵機能のON/OFF比較で技術の価値を示す。定式化の質と同様、効果は補償機構を切った
素の分枝限定で分離して見る。

実行: uv run python experiments/run_improve_redcost.py  ->  results/improve_redcost.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
from pyscipopt import SCIP_PARAMSETTING

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
import knapsack as kp


def nodes(redcost: bool, raw: bool) -> int:
    m = kp.build_model()
    m.hideOutput()
    if raw:
        m.setParam("presolving/maxrounds", 0)
        m.setParam("separating/maxrounds", 0)
        m.setParam("separating/maxroundsroot", 0)
        m.setHeuristics(SCIP_PARAMSETTING.OFF)
    if not redcost:
        m.setParam("propagating/redcost/freq", -1)
        m.setParam("propagating/rootredcost/freq", -1)
    m.optimize()
    return m.getNNodes()


def fig_nodes(raw_on: int, raw_off: int) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=["被約コスト固定 ON(SCIP既定)", "被約コスト固定 OFF"],
        y=[raw_on, raw_off], marker=dict(color=["#0ca30c", "#d03b3b"]),
        text=[raw_on, raw_off], textposition="outside",
        hovertemplate="%{x}<br>ノード数 %{y}<extra></extra>"))
    fig.update_layout(
        title=dict(text="素の分枝限定でのノード数 — 被約コスト固定 ON/OFF",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="ノード数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False, rangemode="tozero"),
        margin=dict(l=60, r=20, t=48, b=44), height=360,
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print("measuring reduced-cost fixing on knapsack ...")
    default_on, default_off = nodes(True, False), nodes(False, False)
    raw_on, raw_off = nodes(True, True), nodes(False, True)
    print(f"  default SCIP: on={default_on} off={default_off}")
    print(f"  raw B&B:      on={raw_on} off={raw_off}")

    reduction = (raw_off - raw_on) / raw_off * 100 if raw_off else 0
    tiles = [
        _tile("素B&B ノード(ON)", f"{raw_on}", good=True),
        _tile("素B&B ノード(OFF)", f"{raw_off}"),
        _tile("ノード削減", f"-{reduction:.0f}%", good=True),
        _tile("既定SCIP(参考)", f"{default_on}ノード"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "improve_redcost.html"
    d1 = fig_nodes(raw_on, raw_off).to_html(full_html=False, include_plotlyjs=True,
                                            config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>被約コスト固定の効果検証</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:130px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:19px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>被約コスト固定の効果検証(Phase 4)</h1>
<div class="sub">knapsack(強相関45品)— SCIP内蔵 redcost 伝播器の価値をON/OFFで確認</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<p class="note">
被約コスト固定は「LP緩和の被約コスト r_j が gap(上界−下界)を超える変数は最適解で値が確定する」
性質を使い変数を永久固定する。<b>SCIPは redcost 伝播器(既定ON)で自動実施</b>するため手動再実装は冗長。
価値を見るため補償機構を切った素の分枝限定で比較すると、<b>ON {raw_on} vs OFF {raw_off} ノード
(−{reduction:.0f}%)</b>と明確に効く。既定SCIPではカット・presolveと併せてこの小問題を{default_on}ノードで解く。
→ 診断は被約コスト固定を「手動実装」ではなく「SCIP既定で有効」として扱うのが正しい(FINDINGS.md 参照)。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
