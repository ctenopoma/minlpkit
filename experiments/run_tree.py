"""空間分枝木の可視化HTMLを生成する (Phase 2.b)

実行: uv run python experiments/run_tree.py --model plant --max-nodes 400
出力: results/tree.html

分枝変数の型で色分け:
  spatial(連続=空間分枝, MINLP固有) / integer / binary / root
ノードのホバーで 下界(双対境界)・分枝変数・深さ を確認できる。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from viz.tree import solve_and_collect

C = dict(surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9", axis="#c3c2b7")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
# dataviz categorical: slot1 blue / slot2 green / slot3 magenta（固定順）
KIND_COLOR = {"spatial": "#2a78d6", "integer": "#008300", "binary": "#e87ba4", "root": "#0b0b0b"}
KIND_LABEL = {"spatial": "空間分枝(連続)", "integer": "整数分枝", "binary": "0-1分枝", "root": "根"}

MODELS = {"uc": "unit_commitment", "sched": "scheduling", "plant": "scheduling_plant"}


def fig_tree(df) -> go.Figure:
    # エッジ(単一トレースにNone区切りで全枝)
    ex, ey = [], []
    xmap = dict(zip(df["node"], df["x"]))
    ymap = dict(zip(df["node"], df["y"]))
    for _, r in df.iterrows():
        p = r["parent"]
        if p in xmap:
            ex += [xmap[p], r["x"], None]
            ey += [ymap[p], r["y"], None]

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=ex, y=ey, mode="lines", line=dict(color=C["grid"], width=1),
                             hoverinfo="skip", showlegend=False))

    # ノード(型ごとに別トレース=凡例に出す)
    for kind in ["spatial", "integer", "binary", "root"]:
        d = df[df["kind"] == kind]
        if d.empty:
            continue
        fig.add_trace(go.Scatter(
            x=d["x"], y=d["y"], mode="markers", name=KIND_LABEL[kind],
            marker=dict(color=KIND_COLOR[kind], size=8 if kind == "root" else 6,
                        line=dict(color=C["surface"], width=1),
                        symbol="square" if kind == "root" else "circle"),
            customdata=d[["node", "depth", "lowerbound", "branch_var", "btype", "bound"]],
            hovertemplate=("ノード%{customdata[0]} / 深さ%{customdata[1]}<br>"
                           "下界 %{customdata[2]:.2f}<br>"
                           "分枝: %{customdata[3]} %{customdata[4]} %{customdata[5]:.3f}<extra></extra>")))

    # incumbent発見ノードを星で重ねる
    inc = df[df["incumbent"]]
    if not inc.empty:
        fig.add_trace(go.Scatter(
            x=inc["x"], y=inc["y"], mode="markers", name="暫定解発見",
            marker=dict(color="#eda100", size=13, symbol="star",
                        line=dict(color=C["surface"], width=1)),
            hovertemplate="このノードで暫定解更新<extra></extra>"))

    fig.update_layout(
        title=dict(text="空間分枝木 — 分枝変数の型で色分け(下方向=深さ)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(visible=False),
        yaxis=dict(title="深さ", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=50, r=16, t=48, b=16), height=520, hovermode="closest",
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def fig_kind_bar(df) -> go.Figure:
    order = ["spatial", "integer", "binary"]
    counts = df[df["kind"] != "root"]["kind"].value_counts()
    vals = [int(counts.get(k, 0)) for k in order]
    fig = go.Figure(go.Bar(
        x=vals, y=[KIND_LABEL[k] for k in order], orientation="h",
        marker=dict(color=[KIND_COLOR[k] for k in order]),
        text=vals, textposition="outside",
        hovertemplate="%{y}: %{x}回<extra></extra>"))
    fig.update_layout(
        title=dict(text="分枝回数の内訳(空間分枝の比率がMINLPの難しさを示す)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="分枝回数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=110, r=40, t=44, b=40), height=240,
    )
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    ap.add_argument("--max-nodes", type=int, default=400, help="描画する分枝ノード数の上限")
    ap.add_argument("--node-limit", type=int, default=3000, help="SCIPの探索ノード上限")
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    model = module.build_model()
    print(f"solving {MODELS[args.model]} (collect up to {args.max_nodes} branch nodes) ...")
    df = solve_and_collect(model, max_nodes=args.max_nodes, node_limit=args.node_limit)

    if df.empty:
        print("分枝ノードが収集されませんでした(ルートで解けた可能性)。--node-limit を上げるか別モデルで試してください。")
        return

    from collections import Counter
    kinds = Counter(df[df["kind"] != "root"]["kind"])
    print(f"collected {len(df)} branch nodes, max depth {int(-df['y'].min())}")
    print(f"branch kinds: spatial={kinds.get('spatial', 0)} integer={kinds.get('integer', 0)} "
          f"binary={kinds.get('binary', 0)}, incumbents={int(df['incumbent'].sum())}")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "tree.html"
    div_tree = fig_tree(df).to_html(full_html=False, include_plotlyjs=True,
                                    config=dict(displayModeBar=False))
    div_bar = fig_kind_bar(df).to_html(full_html=False, include_plotlyjs=False,
                                       config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>空間分枝木</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1040px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
</style></head><body><div class="wrap">
<h1>空間分枝木の可視化(Phase 2.b)</h1>
<div class="sub">{MODELS[args.model]} — 先頭{len(df)}分枝ノード。青=連続変数への空間分枝(非凸緩和を締める)</div>
<div class="card">{div_tree}</div>
<div class="card">{div_bar}</div>
<p class="note">
各点が分枝ノード、下方向が探索の深さ。<b>青(空間分枝)</b>は連続変数(反応時間 tau・反応速度 k 等)の
区間を割る分枝で、McCormick等の凸緩和を締める MINLP 固有の操作。緑=整数分枝、桃=0-1分枝は割当・バッチ数の決定。
黄星は暫定解が更新されたノード。空間分枝の比率が高いほど、非線形緩和の弱さが探索コストを支配していることを示す。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
