"""非線形項の値域(区間演算)の可視化 (Phase 2.c)

plantの各非線形項の値域を区間演算で見積もり、値域スパン(対数)と相対幅で
「どの項の凸緩和が緩くなるか」を静的に予測する。Phase 2.bの違反ヒートマップと突き合わせ可能。

実行: uv run python experiments/run_interval.py  ->  results/interval.html
"""

from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from run_tree import C, FONT
from viz.plant_terms import evaluate_terms

KIND_COLOR = {"energy": "#eb6834", "demand": "#2a78d6", "cooling": "#eda100",
              "conversion": "#008300", "batchtime": "#e87ba4", "arrhenius": "#4a3aa7"}


def fig_ranges(df) -> go.Figure:
    d = df.iloc[::-1]  # 下から相対幅大
    fig = go.Figure()
    for _, r in d.iterrows():
        col = KIND_COLOR.get(r["kind"], "#2a78d6")
        fig.add_trace(go.Scatter(
            x=[r["lo"], r["hi"]], y=[r["term"], r["term"]], mode="lines+markers",
            line=dict(color=col, width=3), marker=dict(color=col, size=9),
            showlegend=False,
            hovertemplate=f"{r['term']}<br>値域 [%{{x:.3g}}]<extra></extra>"))
    fig.update_layout(
        title=dict(text="非線形項の値域スパン(区間演算・対数x)— 広いほど緩和が緩い",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="項の取り得る値(対数)", type="log", gridcolor=C["grid"],
                   linecolor=C["axis"], tickfont=dict(color=C["muted"])),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=180, r=30, t=44, b=40), height=340,
    )
    return fig


def fig_relwidth(df) -> go.Figure:
    d = df.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["rel_width"], y=d["term"], orientation="h",
        marker=dict(color=[KIND_COLOR.get(k, "#2a78d6") for k in d["kind"]]),
        text=[f"{v:.2f}" for v in d["rel_width"]], textposition="outside",
        hovertemplate="%{y}<br>相対幅 %{x:.3f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="相対幅 = 値域幅/(|中点|+1)— 緩和の緩さの静的予測指標",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="相対幅", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=180, r=48, t=44, b=40), height=340,
    )
    return fig


def main() -> None:
    df = evaluate_terms()
    top = df.iloc[0]
    print(f"widest term: {top['term']} rel_width={top['rel_width']:.2f} "
          f"range=[{top['lo']:.3g}, {top['hi']:.3g}]")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "interval.html"
    d1 = fig_ranges(df).to_html(full_html=False, include_plotlyjs=True,
                                config=dict(displayModeBar=False))
    d2 = fig_relwidth(df).to_html(full_html=False, include_plotlyjs=False,
                                  config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>非線形項の値域(区間演算)</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1040px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>非線形項の値域概算(区間演算, Phase 2.c)</h1>
<div class="sub">scheduling_plant — 変数境界だけから各項の値域を区間演算で見積もり、緩和の緩さを静的予測</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
変数境界だけで(solveせず)各非線形項が取り得る値域を区間演算で計算。相対幅が大きい項ほど
凸緩和が緩くなりやすい。<b>最大は <code>energy</code>(n·s·(T−T0), 値域[100, 38400])</b>で、これは
Phase 2.bの違反ヒートマップでenergyが支配的ボトルネックだった観測と一致する(静的予測が動的観測を的中)。
ただし <code>arrhenius</code> は値域は広いが単変数expのためSCIPは緩和をタイトに張れる(違反は小)—
<b>多変数の積(energy/demand/cooling)で「値域が広い×緩和が緩い」が重なる</b>のが真の律速。
Phase 3では energy 等の区分線形近似・変数境界タイト化が候補。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
