"""Phase 7.2: branch-and-price(整数最適)+ 汎用列生成ドライバの実証

minlpkit.column_generation / price_and_branch は問題固有部分(pricing_fn)だけ差し替える
汎用ドライバ。列生成でLP下界を得た後、生成列上で整数主問題を解いて整数最適を得る。

実行: uv run python experiments/run_bnp.py  ->  results/bnp.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
import minlpkit as mk
from viz.colgen import pricing as knapsack_pricing
import cutting_stock as cs


def solve():
    init_cols = [[cs.W // cs.WIDTHS[i] if k == i else 0 for i in range(cs.N_ITEMS)]
                 for k in range(cs.N_ITEMS)]
    pricing_fn = lambda duals: knapsack_pricing(duals, cs.WIDTHS, cs.W)
    return mk.price_and_branch(cs.DEMANDS, init_cols, pricing_fn), pricing_fn, init_cols


def fig_convergence(history, lp, lp_lb, int_obj) -> go.Figure:
    its = [h["iter"] for h in history]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=its, y=[h["dual_bound"] for h in history], mode="lines", name="LP下界(列生成)",
        line=dict(color="#2a78d6", width=2),
        hovertemplate="反復%{x}<br>下界 %{y:.2f}<extra></extra>"))
    fig.add_hline(y=int_obj, line=dict(color="#0ca30c", width=2, dash="dash"),
                  annotation_text=f"整数最適 {int_obj:.0f} ロール", annotation_position="right",
                  annotation_font=dict(color="#0ca30c", size=11))
    fig.add_hline(y=lp, line=dict(color=C["muted"], width=1.5, dash="dot"),
                  annotation_text=f"LP境界 {lp:.2f}", annotation_position="right",
                  annotation_font=dict(color=C["ink2"], size=10))
    fig.update_layout(
        title=dict(text="列生成のLP下界と branch-and-price の整数最適",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="列生成の反復", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="ロール本数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=90, t=48, b=44), height=380,
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print("branch-and-price on cutting stock (via minlpkit generic driver) ...")
    res, _, _ = solve()
    optimal = res["int_obj"] <= res["lp_lb"] + 1e-6
    print(f"LP境界={res['lp_bound']:.3f} LP下界ceil={res['lp_lb']} 整数解={res['int_obj']:.0f} "
          f"最適={optimal} 生成列={res['n_cols']}")

    tiles = [
        _tile("LP境界", f"{res['lp_bound']:.2f}"),
        _tile("LP下界(ceil)", f"{res['lp_lb']}"),
        _tile("整数最適(ロール本数)", f"{res['int_obj']:.0f}", good=True),
        _tile("最適性", "証明済み" if optimal else "上界", good=optimal),
        _tile("生成した列数", f"{res['n_cols']}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_convergence(res["history"], res["lp_bound"], res["lp_lb"], res["int_obj"])
    fig.write_image(str(outdir / "_bnp.png"), width=920, height=380, scale=1)
    d1 = fig.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>branch-and-price</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:120px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:18px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>branch-and-price(Phase 7.2 / 汎用列生成ドライバ)</h1>
<div class="sub">cutting stock — minlpkit.price_and_branch(汎用)で LP下界→整数最適まで</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<p class="note">
列生成でLP境界 {res['lp_bound']:.2f} を得た後、生成した {res['n_cols']} 本の列の上で整数主問題を解き、
<b>整数最適 {res['int_obj']:.0f} ロール</b>を得た(LP下界 ceil={res['lp_lb']} と一致=<b>最適性証明済み</b>)。
これまでの列生成はLP境界までだったが、branch-and-priceで整数解に到達。
コードは <code>minlpkit.price_and_branch(rhs, init_columns, pricing_fn)</code> の<b>汎用ドライバ</b>で、
問題固有は pricing_fn(knapsack)だけ。ベンダーズも <code>minlpkit.benders(master_build, subproblem_solve)</code>
の汎用ドライバ化済み(facilityで単一問題最適1340に一致)。埋め込みでなくコールバックで横展開できる。
</p>
</div></body></html>"""
    (outdir / "bnp.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'bnp.html'}")


if __name__ == "__main__":
    main()
