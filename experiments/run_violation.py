"""非線形制約の違反量ヒートマップを生成する (Phase 2.b)

ルートLP緩和解が各非線形制約をどれだけ違反するか(相対違反)を、
制約タイプ×エンティティ(ジョブ/マシン)のヒートマップと、タイプ別ランキングで示す。
違反が集中する制約 = 凸緩和が最も緩い支配的ボトルネック → Phase 3の再定式化対象。

実行: uv run python experiments/run_violation.py --model plant
出力: results/violation.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.violation import collect_root_violations, violation_by_type

MODELS = {"uc": "unit_commitment", "sched": "scheduling", "plant": "scheduling_plant"}
# dataviz sequential blue(light→dark)。0付近は面へ後退させる
SEQ_BLUE = [[0.0, "#eef5fd"], [0.2, "#cde2fb"], [0.4, "#86b6ef"],
            [0.6, "#3987e5"], [0.8, "#1c5cab"], [1.0, "#0d366b"]]


def fig_heatmap(df) -> go.Figure:
    # 行=タイプ(違反平均降順)、列=エンティティ
    type_order = violation_by_type(df)["ctype"].tolist()
    ent_order = sorted(df["entity"].unique(),
                       key=lambda e: (e[0] != "J", e))  # J* を先、M* を後
    piv = (df.pivot_table(index="ctype", columns="entity", values="rel_violation", aggfunc="max")
           .reindex(index=type_order, columns=ent_order))
    z = piv.values
    text = [["" if v != v else f"{v:.2f}" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=ent_order, y=type_order, colorscale=SEQ_BLUE, zmin=0,
        text=text, texttemplate="%{text}", textfont=dict(size=10),
        colorbar=dict(title=dict(text="相対違反", side="right"), thickness=12,
                      tickfont=dict(color=C["muted"], size=10)),
        hovertemplate="%{y}_%{x}<br>相対違反 %{z:.3f}<extra></extra>",
        xgap=2, ygap=2))
    fig.update_layout(
        title=dict(text="ルートLP緩和解の非線形制約違反(相対)— 濃いほど緩和が緩い",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="ジョブ / マシン", side="top", tickfont=dict(color=C["ink2"])),
        yaxis=dict(autorange="reversed", tickfont=dict(color=C["ink2"])),
        margin=dict(l=90, r=20, t=64, b=16), height=420,
    )
    return fig


def fig_type_bar(df) -> go.Figure:
    g = violation_by_type(df).iloc[::-1]  # 横棒は下から大きく
    fig = go.Figure(go.Bar(
        x=g["mean_rel"], y=g["ctype"], orientation="h",
        marker=dict(color="#2a78d6"),
        text=[f"{v:.2f}" for v in g["mean_rel"]], textposition="outside",
        customdata=g[["max_rel", "n"]],
        hovertemplate="%{y}<br>平均相対違反 %{x:.3f}<br>最大 %{customdata[0]:.3f} / %{customdata[1]}本<extra></extra>"))
    fig.update_layout(
        title=dict(text="制約タイプ別の平均相対違反(支配的ボトルネックの特定)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="平均相対違反", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=90, r=48, t=44, b=40), height=300,
    )
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    model = module.build_model()
    print(f"collecting root LP violations for {MODELS[args.model]} ...")
    df = collect_root_violations(model)
    if df.empty:
        print("非線形制約が検出されませんでした(このモデルはLPで解ける可能性)。")
        return

    top = violation_by_type(df).iloc[0]
    print(f"constraints={len(df)}  dominant bottleneck: {top['ctype']} "
          f"(mean rel viol {top['mean_rel']:.2f})")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "violation.html"
    d1 = fig_heatmap(df).to_html(full_html=False, include_plotlyjs=True,
                                 config=dict(displayModeBar=False))
    d2 = fig_type_bar(df).to_html(full_html=False, include_plotlyjs=False,
                                  config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>非線形制約の違反量</title>
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
<h1>非線形制約の違反量ヒートマップ(Phase 2.b)</h1>
<div class="sub">{MODELS[args.model]} — ルートLP緩和解を真の非線形制約に代入した相対違反</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
相対違反 = 違反量 / (|活動値|+1)。濃い(大きい)ほど、その制約の凸緩和がルートで真の値から離れている
= <b>双対境界を押し下げる支配的ボトルネック</b>。plantでは <code>energy</code>(三重積 n·s·(T−T0))と
<code>conversion</code>(ネストexp)が緩く、<code>arrhenius</code>/<code>tmax</code>/<code>jobtime</code> は
ほぼタイト。これは Phase 2.c で空間分枝が <code>t_k</code>・<code>t_tau</code> に集中した所見と整合する。
Phase 3の改善候補: energy/conversion の<b>区分線形近似・凸包再定式化・変数境界タイト化</b>。
<br>※ 線形制約のIIS/スラック可視化は、このモデルでは全線形制約がpresolveで非線形/varboundに吸収され
純粋な線形制約が残らないため対象外(別モデルで別途)。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
