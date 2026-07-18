"""Phase 4: Big-M改善(loose→tight/indicator)の効果検証

診断 numerical_scale/Big-M の推薦「Big-M排除(Indicator/SOS)」を実施し、
before(緩いBig-M)/ after(tight・indicator)を比較する。
指標: 純粋LP緩和境界(定式化の質)と素のB&Bノード数(下流効果)。

実行: uv run python experiments/run_improve_bigm.py  ->  results/improve_bigm.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
from pyscipopt import SCIP_PARAMSETTING

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
import fixed_charge as fc

VARIANTS = ["loose", "tight", "indicator"]
LABEL = {"loose": "緩いBig-M(before)", "tight": "tight Big-M(after)",
         "indicator": "Indicator制約(after)"}
COLOR = {"loose": "#d03b3b", "tight": "#0ca30c", "indicator": "#2a78d6"}


def raw_nodes(bigm: str) -> int:
    """素の分枝限定(presolve/cut/heur off)でのノード数=定式化の質の下流効果。"""
    m = fc.build_model(bigm)
    m.hideOutput()
    m.setParam("presolving/maxrounds", 0)
    m.setParam("separating/maxrounds", 0)
    m.setParam("separating/maxroundsroot", 0)
    m.setHeuristics(SCIP_PARAMSETTING.OFF)
    m.optimize()
    return m.getNNodes()


def optimal() -> float:
    m = fc.build_model("tight")
    m.hideOutput()
    m.optimize()
    return m.getObjVal()


def fig_lp_bound(bounds: dict, opt: float) -> go.Figure:
    xs = [LABEL[v] for v in VARIANTS]
    ys = [bounds[v] for v in VARIANTS]
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker=dict(color=[COLOR[v] for v in VARIANTS]),
        text=[f"{y:.0f}" for y in ys], textposition="outside",
        hovertemplate="%{x}<br>LP緩和境界 %{y:.0f}<extra></extra>"))
    fig.add_hline(y=opt, line=dict(color=C["muted"], width=2, dash="dash"),
                  annotation_text=f"最適値 {opt:.0f}", annotation_position="top right",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="純粋LP緩和境界(大=強い緩和=最適値に近い)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="LP緩和境界", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=20, t=48, b=44), height=380,
    )
    return fig


def fig_nodes(nodes: dict) -> go.Figure:
    xs = [LABEL[v] for v in VARIANTS]
    ys = [nodes[v] for v in VARIANTS]
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker=dict(color=[COLOR[v] for v in VARIANTS]),
        text=ys, textposition="outside",
        hovertemplate="%{x}<br>ノード数 %{y}<extra></extra>"))
    fig.update_layout(
        title=dict(text="素の分枝限定でのノード数(presolve/cut off・定式化の下流効果)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="ノード数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=20, t=44, b=44), height=320,
    )
    return fig


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def main() -> None:
    print("measuring Big-M formulations ...")
    bounds = {v: fc.lp_relaxation_bound(v) for v in VARIANTS}
    nodes = {v: raw_nodes(v) for v in VARIANTS}
    opt = optimal()
    for v in VARIANTS:
        print(f"  {v:10s}: LP={bounds[v]:.0f}  raw_nodes={nodes[v]}  "
              f"(最適との差 {opt - bounds[v]:.0f})")

    improve_pct = (bounds["tight"] - bounds["loose"]) / bounds["loose"] * 100
    tiles = [
        _tile("緩いBig-M LP境界", f"{bounds['loose']:.0f}"),
        _tile("tight LP境界", f"{bounds['tight']:.0f}"),
        _tile("最適値", f"{opt:.0f}"),
        _tile("緩和の改善", f"+{improve_pct:.0f}%"),
        _tile("ノード削減(素B&B)", f"{nodes['loose']}→{nodes['tight']}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "improve_bigm.html"
    d1 = fig_lp_bound(bounds, opt).to_html(full_html=False, include_plotlyjs=True,
                                           config=dict(displayModeBar=False))
    d2 = fig_nodes(nodes).to_html(full_html=False, include_plotlyjs=False,
                                  config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>Big-M改善の効果検証</title>
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
<h1>Big-M改善の効果検証(Phase 4)</h1>
<div class="sub">診断 numerical_scale の推薦「Big-M排除(Indicator/SOS)」を fixed_charge モデルで実施・検証</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
連動制約 <code>x_i ≤ M_i·y_i</code> の Big-M を、緩い巨大定数(before)から実際の最大生産量=min(容量,需要)
(tight)や <b>Indicator制約</b>(y_i=0 ⟹ x_i=0)に置き換えた。純粋LP緩和境界が
<b>{bounds['loose']:.0f} → {bounds['tight']:.0f}(+{improve_pct:.0f}%、最適値{opt:.0f}にほぼ到達)</b>と大幅に締まる。
素の分枝限定ではノードが {nodes['loose']}→{nodes['tight']} に減る。
<br>※ デフォルトのSCIPはpresolveが緩いBig-Mを自動的に締めるため、この小規模例では最終解時間は変わらない
(SCIPが賢い)。定式化の質は大規模問題やpresolveが効きにくい構造で効いてくる。診断→改善→検証の
一連の流れとして、Big-M排除が緩和を強めることを定量的に確認できた。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
