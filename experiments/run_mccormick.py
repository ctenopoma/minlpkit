"""McCormick 包絡の締まりアニメーションHTMLを生成する (Phase 2.a)

非凸双線形項 z=x·y の真の曲面と、x区間をk分割した区分McCormick凸下界を
3Dで重ね、スライダーで分割数kを動かすと緩和が締まる様子を見せる。
併せて「最大緩和ギャップ vs 分割数」を2Dで定量表示する。

実行: uv run python experiments/run_mccormick.py  ->  results/mccormick.html
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import plotly.graph_objects as go

from viz.mccormick import Box, max_gap, piecewise_underestimator, true_surface

# 参照パレット (dataviz, light)
C = dict(surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9", axis="#c3c2b7", s1="#2a78d6", s2="#008300")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

BOX: Box = (-2.0, 2.0, -2.0, 2.0)  # 対称box → z=x·y が古典的な鞍型に
KS = [1, 2, 3, 4, 6, 8]
NX, NY = 72, 72


def _surfaces(k: int) -> list[go.Surface]:
    xL, xU, yL, yU = BOX
    xg, yg = np.linspace(xL, xU, NX), np.linspace(yL, yU, NY)
    Zt = true_surface(xg, yg)
    Zu = piecewise_underestimator(xg, yg, BOX, k)
    # 真の曲面(グレー・半透明)/ McCormick凸下界(青)
    return [
        go.Surface(x=xg, y=yg, z=Zt, name="真の曲面 z=x·y", showscale=False, opacity=0.55,
                   colorscale=[[0, C["muted"]], [1, C["muted"]]], hoverinfo="skip"),
        go.Surface(x=xg, y=yg, z=Zu, name="McCormick凸下界", showscale=False, opacity=0.95,
                   colorscale=[[0, "#9ec5f4"], [1, C["s1"]]],
                   contours=dict(x=dict(show=True, color="rgba(255,255,255,0.4)", width=1,
                                        start=xL, end=xU, size=(xU - xL) / k)),
                   hovertemplate="下界 %{z:.2f}<extra></extra>"),
    ]


def build_fig() -> go.Figure:
    frames = [go.Frame(data=_surfaces(k), name=str(k),
                       layout=go.Layout(
                           title=dict(text=f"McCormick凸緩和 — x区間を <b>{k}分割</b>　"
                                           f"最大ギャップ = {max_gap(BOX, k):.3f}"))) for k in KS]
    fig = go.Figure(data=_surfaces(KS[0]), frames=frames)

    steps = [dict(method="animate", label=f"{k}分割",
                  args=[[str(k)], dict(mode="immediate", frame=dict(duration=0, redraw=True),
                                       transition=dict(duration=0))]) for k in KS]
    fig.update_layout(
        title=dict(text=f"McCormick凸緩和 — x区間を <b>{KS[0]}分割</b>　"
                        f"最大ギャップ = {max_gap(BOX, KS[0]):.3f}",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], font=dict(family=FONT, color=C["ink2"], size=12),
        scene=dict(
            xaxis=dict(title="x", backgroundcolor=C["surface"], gridcolor=C["grid"],
                       color=C["muted"], zeroline=False),
            yaxis=dict(title="y", backgroundcolor=C["surface"], gridcolor=C["grid"],
                       color=C["muted"], zeroline=False),
            zaxis=dict(title="z", backgroundcolor=C["surface"], gridcolor=C["grid"],
                       color=C["muted"], zeroline=False),
            aspectmode="cube",
            camera=dict(eye=dict(x=1.6, y=1.6, z=1.15)),
        ),
        margin=dict(l=0, r=0, t=48, b=8), height=560, showlegend=False,
        sliders=[dict(active=0, x=0.05, len=0.9, y=0.02, pad=dict(t=4, b=4),
                      currentvalue=dict(prefix="分割数 k = ", font=dict(color=C["ink2"])),
                      steps=steps)],
        updatemenus=[dict(type="buttons", showactive=False, x=0.05, y=0.14, xanchor="right",
                          buttons=[dict(label="▶ 再生", method="animate",
                                        args=[None, dict(frame=dict(duration=700, redraw=True),
                                                         fromcurrent=True,
                                                         transition=dict(duration=0))])])],
    )
    return fig


def fig_gap_curve() -> go.Figure:
    ks = list(range(1, 13))
    gaps = [max_gap(BOX, k) for k in ks]
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=ks, y=gaps, mode="lines+markers", line=dict(color=C["s1"], width=2),
        marker=dict(size=8, color=C["s1"], line=dict(color=C["surface"], width=2)),
        hovertemplate="k=%{x}分割<br>最大ギャップ %{y:.3f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="最大緩和ギャップ vs 分割数(∝ 1/k で締まる)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="分割数 k", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), dtick=1, zeroline=False),
        yaxis=dict(title="最大ギャップ", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), rangemode="tozero", zeroline=False),
        margin=dict(l=60, r=20, t=44, b=44), height=320,
    )
    return fig


def main() -> None:
    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "mccormick.html"
    div_3d = build_fig().to_html(full_html=False, include_plotlyjs=True,
                                 config=dict(displayModeBar=False))
    div_gap = fig_gap_curve().to_html(full_html=False, include_plotlyjs=False,
                                      config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>McCormick緩和の締まり</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>McCormick凸緩和の締まり(Phase 2.a)</h1>
<div class="sub">非凸な双線形項 z=x·y を空間分枝限定法がどう緩和し、区間分割で締めるか</div>
<div class="card">{div_3d}</div>
<div class="card">{div_gap}</div>
<p class="note">
グレーが真の曲面 <code>z=x·y</code>(鞍型=非凸)、青が x 区間を k 分割した区分McCormick凸下界。
スライダー(または▶再生)で分割数を上げると、下界が真の曲面に貼り付き最大ギャップが縮む。
これが spatial branching が双対境界を押し上げる仕組みそのもの。ギャップは 1分割で
(Δx·Δy)/4 = 4.0、k分割で約 4.0/k。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
