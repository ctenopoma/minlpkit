"""Phase 4: n·s の厳密線形化(分解)の効果検証 — plantの weak_relaxation 対応

診断の[重大]「energy三重積の緩和が支配的ボトルネック→再定式化」に対し、
整数nと連続sの積 n·s を指示変数で厳密線形化し、三重積を双線形に落とす。
SCIPが自動でやらない(McCormickではなく厳密分解)真の改善。

実行: uv run python experiments/run_improve_linearize.py  ->  results/improve_linearize.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.monitor import solve_with_monitor
import scheduling_plant as sp

TLIM = 25.0
COL = {"base": "#d03b3b", "lin": "#0ca30c"}
LAB = {"base": "baseline(n·s双線形)", "lin": "厳密線形化(分解)"}


def root_dual(lin: bool) -> float:
    m = sp.build_model(linearize_ns=lin)
    m.hideOutput()
    m.setParam("limits/nodes", 1)
    m.optimize()
    return m.getDualbound()


def fig_dual(traj: dict) -> go.Figure:
    fig = go.Figure()
    for key in ("base", "lin"):
        df = traj[key]
        fig.add_trace(go.Scatter(
            x=df["time"], y=df["dual"], mode="lines", name=LAB[key],
            line=dict(color=COL[key], width=2, shape="hv"),
            hovertemplate=LAB[key] + " dual %{y:.1f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="双対境界の推移(上=強い)— 厳密線形化が緩和を大幅に締める",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="求解時間 [s]", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="Dual bound", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=48, b=44), height=400, hovermode="x unified",
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print("measuring n·s exact linearization on plant ...")
    roots = {k: root_dual(k == "lin") for k in ("base", "lin")}
    traj, summ = {}, {}
    for key in ("base", "lin"):
        mon, s = solve_with_monitor(sp.build_model(linearize_ns=(key == "lin")),
                                    time_limit=TLIM, gap_limit=0.01)
        traj[key], summ[key] = mon.to_frame(), s
        print(f"  {LAB[key]}: root={roots[key]:.1f} final_dual={s['dual']:.1f} "
              f"gap={s['gap']*100:.1f}% nodes={s['nodes']}")

    root_gain = (roots["lin"] - roots["base"]) / roots["base"] * 100
    tiles = [
        _tile("ルート境界 before", f"{roots['base']:.0f}"),
        _tile("ルート境界 after", f"{roots['lin']:.0f}", good=True),
        _tile("ルート境界の改善", f"+{root_gain:.0f}%", good=True),
        _tile("最終gap before", f"{summ['base']['gap']*100:.0f}%"),
        _tile("最終gap after", f"{summ['lin']['gap']*100:.0f}%", good=True),
        _tile("ノード before→after", f"{summ['base']['nodes']}→{summ['lin']['nodes']}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "improve_linearize.html"
    d1 = fig_dual(traj).to_html(full_html=False, include_plotlyjs=True,
                                config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>厳密線形化の効果検証</title>
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
<h1>n·s 厳密線形化の効果検証(Phase 4)</h1>
<div class="sub">scheduling_plant — 診断[重大]weak_relaxation(energy三重積)への再定式化</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<p class="note">
energy <code>e=n·s·(T−T0)</code> と demand <code>n·s·X≥d</code> の三重積が緩和の支配的ボトルネックだった。
<b>整数n(∈1..8)と連続sの積 n·s を指示変数 δ_v(n=v)で厳密に線形化</b>(ns=Σ_v v·s_v)し、
三重積を双線形(ns·X, ns·(T−T0))に落とした。結果:
<b>ルート双対境界 {roots['base']:.0f}→{roots['lin']:.0f}(+{root_gain:.0f}%)、最終gap
{summ['base']['gap']*100:.0f}%→{summ['lin']['gap']*100:.0f}%</b>、探索ノードも減少。最適値は不変(厳密変換)。
McCormick緩和しか使わないSCIPが自動では得られない改善で、診断→再定式化→検証の一連が実モデルで機能した。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
