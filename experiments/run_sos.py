"""SOS2区分線形近似(Big-M回避)の効果検証

非凸関数 f(x) を区分線形近似して最小化。SOS2(隣接2重み)版と Big-M(セグメントバイナリ)版が
同じ最適値になり、SOS2はバイナリ/Big-M定数を使わずに済む(SCIP native SOS2分岐)ことを示す。

実行: uv run python experiments/run_sos.py  ->  results/sos.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
import pwl_sos as pw


def _model_stats(method: str) -> dict:
    m = pw.build_model(method)
    n_bin = sum(1 for v in m.getVars() if v.vtype() == "BINARY")
    m.hideOutput()
    m.optimize()
    return dict(x=m.getVal(m.data["x"]), y=m.getObjVal(), nodes=m.getNNodes(),
               n_vars=m.getNVars(), n_bin=n_bin, n_cons=m.getNConss())


def fig_function(xstar, fstar, x_opt, y_opt) -> go.Figure:
    xs, ys = pw.breakpoints()
    grid = [pw.X_LO + (pw.X_HI - pw.X_LO) * i / 400 for i in range(401)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=grid, y=[pw.f(x) for x in grid], mode="lines",
                             name="真の関数 f(x)", line=dict(color=C["muted"], width=2)))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name="区分線形近似(折れ点)",
                             line=dict(color="#2a78d6", width=2),
                             marker=dict(size=5, color="#2a78d6")))
    fig.add_trace(go.Scatter(x=[x_opt], y=[y_opt], mode="markers", name="SOS2が見つけた最小",
                             marker=dict(color="#0ca30c", size=13, symbol="star",
                                         line=dict(color=C["surface"], width=1))))
    fig.add_trace(go.Scatter(x=[xstar], y=[fstar], mode="markers", name="真の最小",
                             marker=dict(color="#d03b3b", size=9, symbol="circle-open",
                                         line=dict(width=2))))
    fig.update_layout(
        title=dict(text="非凸関数の区分線形近似とSOS2による最小化",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="x", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="f(x)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=48, b=44), height=380,
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    grid = [pw.X_LO + (pw.X_HI - pw.X_LO) * i / 2000 for i in range(2001)]
    xstar = min(grid, key=pw.f)
    fstar = pw.f(xstar)
    sos = _model_stats("sos2")
    bigm = _model_stats("bigm")
    print(f"真の最小 x*={xstar:.3f} f={fstar:.4f}")
    print(f"sos2: x={sos['x']:.3f} y={sos['y']:.4f} bin={sos['n_bin']} vars={sos['n_vars']}")
    print(f"bigm: x={bigm['x']:.3f} y={bigm['y']:.4f} bin={bigm['n_bin']} vars={bigm['n_vars']}")

    tiles = [
        _tile("真の最小 f(x*)", f"{fstar:.3f}"),
        _tile("SOS2の解", f"{sos['y']:.3f}", good=abs(sos["y"] - bigm["y"]) < 1e-6),
        _tile("SOS2のバイナリ数", f"{sos['n_bin']}", good=True),
        _tile("Big-M版のバイナリ数", f"{bigm['n_bin']}"),
        _tile("変数数 SOS2/BigM", f"{sos['n_vars']}/{bigm['n_vars']}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_function(xstar, fstar, sos["x"], sos["y"])
    fig.write_image(str(outdir / "_sos.png"), width=900, height=380, scale=1)  # 検証用
    d1 = fig.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>SOS2区分線形近似の効果検証</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:130px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:18px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>SOS2 区分線形近似(Big-M回避)</h1>
<div class="sub">非凸関数 f(x)=sin(1.5x)+0.15(x−5)² を{pw.N_BREAK}折れ点でPWL近似し最小化</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<p class="note">
区分線形関数は「隣接する2つの折れ点の凸結合」で表せる。重み λ_k に <b>SOS2制約(隣接2つまで非ゼロ)</b>を
課すと、Big-M(セグメントごとのバイナリ)を使わずにPWLを表現できる。
<b>SOS2版はバイナリ {sos['n_bin']}個(SCIP native SOS2分岐)</b>に対し、
<b>Big-M版はバイナリ {bigm['n_bin']}個</b>を要する。両者は同じ最適値 {sos['y']:.3f} に到達
(真の最小 {fstar:.3f} との差はPWL近似誤差)。Indicator制約と並ぶ Big-M回避の手段で、
診断の「区分線形近似」推薦の実装選択肢になる。折れ点を増やせば近似精度は上がる。
</p>
</div></body></html>"""
    (outdir / "sos.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'sos.html'}")


if __name__ == "__main__":
    main()
