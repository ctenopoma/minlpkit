"""Phase 6: ベンダーズ分解の効果検証(facility)

主問題(施設開設)/サブ問題(輸送LP)に分解し、最適性カットで下界を押し上げて
単一問題と同じ最適値に収束することを示す。診断 decomposable への実装対応。

実行: uv run python experiments/run_benders.py  ->  results/benders.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.benders import benders, monolithic_optimum


def fig_convergence(hist, mono) -> go.Figure:
    its = [h["iter"] for h in hist]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=its, y=[h["ub"] for h in hist], mode="lines+markers", name="上界 UB(最良の実行可能解)",
        line=dict(color="#d03b3b", width=2), marker=dict(size=8, color="#d03b3b",
                                                         line=dict(color=C["surface"], width=2)),
        hovertemplate="反復%{x}<br>UB %{y:.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=its, y=[h["lb"] for h in hist], mode="lines+markers", name="下界 LB(主問題)",
        line=dict(color="#2a78d6", width=2), marker=dict(size=8, color="#2a78d6",
                                                         line=dict(color=C["surface"], width=2)),
        hovertemplate="反復%{x}<br>LB %{y:.1f}<extra></extra>"))
    fig.add_hline(y=mono, line=dict(color=C["muted"], width=2, dash="dash"),
                  annotation_text=f"単一問題の最適値 {mono:.0f}", annotation_position="right",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="ベンダーズ反復の収束 — 下界(主問題)が最適性カットで上界に到達",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="反復(=追加した最適性カット数)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), dtick=1, zeroline=False),
        yaxis=dict(title="目的関数値(総費用)", gridcolor=C["grid"], linecolor=C["axis"],
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
    print("running Benders decomposition on facility ...")
    mono = monolithic_optimum()
    res = benders()
    match = abs(res["ub"] - mono) < 1e-4
    print(f"monolithic={mono:.1f}  benders UB={res['ub']:.1f} LB={res['lb']:.1f} "
          f"cuts={res['n_cuts']} iters={len(res['history'])} match={match}")

    tiles = [
        _tile("単一問題の最適値", f"{mono:.0f}"),
        _tile("ベンダーズ最適値", f"{res['ub']:.0f}", good=match),
        _tile("最適性カット数", f"{res['n_cuts']}"),
        _tile("反復回数", f"{len(res['history'])}"),
        _tile("開設施設", ", ".join(i for i, v in res["best_y"].items() if v == 1)),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_convergence(res["history"], mono)
    fig.write_image(str(outdir / "_benders.png"), width=900, height=400, scale=1)  # 検証用
    d1 = fig.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>ベンダーズ分解の効果検証</title>
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
<h1>ベンダーズ分解の効果検証(Phase 6 / 診断: decomposable)</h1>
<div class="sub">facility(施設配置)を 主問題(開設 y)/サブ問題(輸送LP)に分解して求解</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<p class="note">
主問題は施設開設 y_i(整数)と輸送費の下界 η を決め、サブ問題は ŷ を固定した輸送LPを解く。
サブ問題の容量制約の双対から <b>最適性カット η ≥ Q(ŷ) + Σg_i(y_i−ŷ_i)</b> を主問題へ返す(scipy linprogで双対取得)。
<b>下界(主問題)が {res['history'][0]['lb']:.0f}→{res['lb']:.0f} と上昇し、単一問題の最適値 {mono:.0f} に一致して収束</b>
({res['n_cuts']}カット・{len(res['history'])}反復)。診断が「ブロック構造+少数結合制約→分解可能」と推薦した対応の実装。
実務では主問題が小さく保たれ、サブ問題は独立に(並列に)解ける利点がある。
</p>
</div></body></html>"""
    (outdir / "benders.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'benders.html'}")


if __name__ == "__main__":
    main()
