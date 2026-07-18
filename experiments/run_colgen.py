"""Phase 4: 列生成(Gilmore-Gomory)の効果検証 — cutting stock

列生成の真の価値は「指数的に多いパターン(列)を列挙せず、pricingで必要な列だけ生成して
最適LP境界に到達する」こと。LP境界自体はコンパクト定式化と同等(ともに材料下界)だが、
列生成は全列を持たずに解ける=SCIPが自動でやらない、モデラーが与える再定式化。

実行: uv run python experiments/run_colgen.py  ->  results/colgen.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.colgen import column_generation
import cutting_stock as cs


def count_patterns(widths: list[int], W: int) -> int:
    ws = sorted(set(widths))

    def rec(idx: int, rem: int) -> int:
        if idx == len(ws):
            return 1
        return sum(rec(idx + 1, rem - k * ws[idx]) for k in range(rem // ws[idx] + 1))

    return rec(0, W) - 1


def fig_bound(hist, material) -> go.Figure:
    its = [h["iter"] for h in hist]
    lb = [h["lp_bound"] for h in hist]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=its, y=lb, mode="lines+markers", name="master LP境界",
        line=dict(color="#2a78d6", width=2),
        marker=dict(size=8, color="#2a78d6", line=dict(color=C["surface"], width=2)),
        hovertemplate="反復%{x}<br>LP境界 %{y:.3f}<extra></extra>"))
    fig.add_hline(y=material, line=dict(color=C["muted"], width=2, dash="dash"),
                  annotation_text=f"材料下界 {material:.2f}", annotation_position="bottom right",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="master LP境界の収束(列を追加するたび締まる)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(title="列生成の反復", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), dtick=1, zeroline=False),
        yaxis=dict(title="LP境界(ロール本数)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=48, b=44), height=360,
    )
    return fig


def fig_pricing(hist) -> go.Figure:
    its = [h["iter"] for h in hist]
    pv = [h["pricing_val"] for h in hist]
    fig = go.Figure(go.Scatter(
        x=its, y=pv, mode="lines+markers", line=dict(color="#008300", width=2),
        marker=dict(size=8, color="#008300", line=dict(color=C["surface"], width=2)),
        hovertemplate="反復%{x}<br>pricing値 %{y:.3f}<extra></extra>"))
    fig.add_hline(y=1.0, line=dict(color="#d03b3b", width=2, dash="dash"),
                  annotation_text="収束閾値 1.0(これ以下で停止)", annotation_position="top right",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="pricing(価格付け)値 — 1.0に達すると改善列なし=収束",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="列生成の反復", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), dtick=1, zeroline=False),
        yaxis=dict(title="pricingナップサック最適値", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=44, b=44), height=320,
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print("running column generation on cutting stock ...")
    res = column_generation(cs.WIDTHS, cs.DEMANDS, cs.W)
    material = sum(cs.WIDTHS[i] * cs.DEMANDS[i] for i in range(cs.N_ITEMS)) / cs.W
    total = count_patterns(cs.WIDTHS, cs.W)
    gen = res["n_patterns"]
    print(f"GG LP bound={res['lp_bound']:.3f}  iters={len(res['history'])}  "
          f"patterns {gen}/{total} ({gen/total*100:.1f}%)")

    tiles = [
        _tile("GG LP境界", f"{res['lp_bound']:.2f}"),
        _tile("材料下界", f"{material:.2f}"),
        _tile("総パターン数", f"{total}"),
        _tile("生成したパターン", f"{gen}({gen/total*100:.0f}%)", good=True),
        _tile("反復回数", f"{len(res['history'])}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "colgen.html"
    d1 = fig_bound(res["history"], material).to_html(full_html=False, include_plotlyjs=True,
                                                     config=dict(displayModeBar=False))
    d2 = fig_pricing(res["history"]).to_html(full_html=False, include_plotlyjs=False,
                                             config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>列生成の効果検証</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:120px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:19px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>列生成(Gilmore-Gomory)の効果検証(Phase 4)</h1>
<div class="sub">cutting stock — 診断 decomposable への対応。指数的な列を暗黙に扱う再定式化</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
制限付き主問題(連続LP)を解いて双対πを得て、pricingナップサック
<code>max Σπ_i a_i s.t. Σw_i a_i≤W</code> で被約コスト負のパターンを生成、を繰り返す。
<b>総実行可能パターン {total}個のうち {gen}個({gen/total*100:.0f}%)だけ生成して最適LP境界 {res['lp_bound']:.2f} に到達</b>。
LP境界自体はコンパクト定式化(材料下界 {material:.2f})と同等だが、列生成は<b>全列を持たずに解ける</b>のが本質。
実務ではパターンが数百万〜指数的でコンパクト定式化は構築すら不能な規模でも、pricingで必要な列だけ生成して解ける。
SCIPが自動ではやらない(モデラーが主問題/pricingを与える)真の再定式化。診断のブロック構造/結合制約(→分解)に対応。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
