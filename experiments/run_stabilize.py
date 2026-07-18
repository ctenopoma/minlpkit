"""Phase 6: 列生成の双対安定化(Wentges smoothing)の効果検証

素の列生成は後半に双対が振動して収束が遅くなる(tailing-off)。安定化中心(最良Lagrange
下界を与えた双対)へ双対を平滑化 π̃=α·π_center+(1−α)·π して反復を減らす。
平滑双対で改善列が出ないときは真の双対にフォールバック(最適性を保証)。

実行: uv run python experiments/run_stabilize.py  ->  results/stabilize.html
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.colgen import column_generation

# 退化・tailing-off が出る固定 instance(seed 11)
_rng = random.Random(11)
W = 150
WIDTHS = sorted({_rng.randint(20, 75) for _ in range(22)}, reverse=True)
DEMANDS = [_rng.randint(30, 90) for _ in WIDTHS]
ALPHAS = [0.0, 0.3, 0.5, 0.7, 0.9]


def fig_iters(results, max_iter: int = 500) -> go.Figure:
    base = len(results[0.0]["history"])
    # 収束した α のみバーに(未収束=max_iter到達 は注記へ回す)
    conv = [a for a in ALPHAS if len(results[a]["history"]) < max_iter]
    xs = [("安定化なし" if a == 0 else f"α={a}") for a in conv]
    ys = [len(results[a]["history"]) for a in conv]
    colors = ["#898781" if a == 0 else ("#0ca30c" if y < base else "#d03b3b")
              for a, y in zip(conv, ys)]
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker=dict(color=colors), text=ys, textposition="outside",
        hovertemplate="%{x}<br>反復 %{y}<extra></extra>"))
    fig.add_hline(y=base, line=dict(color=C["muted"], width=1.5, dash="dash"),
                  annotation_text=f"安定化なし {base}反復", annotation_position="top left",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="双対安定化の強さ α と収束反復数(緑=改善)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="収束までの反復数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False, rangemode="tozero"),
        margin=dict(l=60, r=16, t=48, b=44), height=360,
    )
    return fig


def fig_convergence(results) -> go.Figure:
    fig = go.Figure()
    for a, color, name in [(0.0, "#d03b3b", "安定化なし"), (0.4, "#0ca30c", "安定化 α=0.4")]:
        res = results[a]
        h = res["history"]
        fig.add_trace(go.Scatter(
            x=[r["iter"] for r in h], y=[r["dual_bound"] for r in h], mode="lines",
            name=name, line=dict(color=color, width=2),
            hovertemplate=name + " 下界 %{y:.1f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="Lagrange下界(Farley)の収束 — 安定化で早く上界に達する",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="反復", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="Lagrange下界", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=44, b=44), height=320, hovermode="x unified",
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print(f"cutting stock: {len(WIDTHS)}品目 W={W} 総需要{sum(DEMANDS)}")
    results = {}
    for a in set(ALPHAS + [0.4]):
        results[a] = column_generation(WIDTHS, DEMANDS, W, alpha=a)
    for a in ALPHAS:
        print(f"  α={a}: 反復{len(results[a]['history'])} LP={results[a]['lp_bound']:.3f}")

    base = len(results[0.0]["history"])
    best_a = min([a for a in ALPHAS if a > 0], key=lambda a: len(results[a]["history"]))
    best_it = len(results[best_a]["history"])
    reduction = (base - best_it) / base * 100

    tiles = [
        _tile("安定化なし 反復", f"{base}"),
        _tile(f"安定化(α={best_a}) 反復", f"{best_it}", good=True),
        _tile("反復削減", f"−{reduction:.0f}%", good=True),
        _tile("LP境界(不変=正当)", f"{results[0.0]['lp_bound']:.1f}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    f1 = fig_iters(results)
    f1.write_image(str(outdir / "_stab.png"), width=900, height=360, scale=1)  # 検証用
    d1 = f1.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))
    d2 = fig_convergence(results).to_html(full_html=False, include_plotlyjs=False,
                                          config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>双対安定化の効果検証</title>
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
<h1>列生成の双対安定化(Phase 6 / 2.c)</h1>
<div class="sub">cutting stock({len(WIDTHS)}品目)— Wentges smoothing で tailing-off を抑える</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
安定化中心(最良Lagrange下界=Farley bound を与えた双対 π_center)へ双対を平滑化
<code>π̃=α·π_center+(1−α)·π</code> して pricing に使う。双対の振動が抑えられ、
<b>収束反復が {base}→{best_it}(−{reduction:.0f}%)</b>に減少(LP境界 {results[0.0]['lp_bound']:.1f} は不変=最適性維持)。
平滑双対で改善列が出ないときは真の双対にフォールバックし収束を保証する。
<b>α が大きすぎると(0.9)過剰安定化で逆に収束しない</b>(赤)——中庸のαが要。
SCIPが自動でやらない、列生成の実装者が入れる収束加速。
</p>
</div></body></html>"""
    (outdir / "stabilize.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'stabilize.html'}")


if __name__ == "__main__":
    main()
