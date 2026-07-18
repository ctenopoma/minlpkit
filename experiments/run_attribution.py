"""双対境界改善の分枝変数への帰属を可視化する (Phase 2.c)

Phase 1(双対境界の推移)と Phase 2.b(分枝変数)を1画面で結合し、
「gap停滞を抜けた瞬間にどの分枝が効いたか」「空間分枝と離散分枝の
どちらが境界を押し上げているか」を見せる。

実行: uv run python experiments/run_attribution.py --model plant --time 30
出力: results/attribution.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT, KIND_COLOR, KIND_LABEL
from viz.attribution import (detect_stalls, gain_by_kind, gain_by_variable,
                             solve_and_attribute)

MODELS = {"uc": "unit_commitment", "sched": "scheduling", "plant": "scheduling_plant"}


def fig_dual_attr(d, stalls) -> go.Figure:
    fig = go.Figure()
    # 停滞区間を淡くシェード
    for a, b in stalls:
        fig.add_vrect(x0=a, x1=b, fillcolor="rgba(137,135,129,0.12)",
                      line_width=0, layer="below")
    # 双対境界の推移
    fig.add_trace(go.Scatter(
        x=d["time"], y=d["dual"], mode="lines", name="Dual bound",
        line=dict(color="#008300", width=2),
        hovertemplate="dual %{y:.2f}<extra></extra>"))
    # 有意な改善点を型別に色分けして重ねる
    thr = d["dual_gain"].sum() * 0.01
    imp = d[d["dual_gain"] >= thr]
    for kind in ["spatial", "integer", "binary"]:
        dk = imp[imp["kind"] == kind]
        if dk.empty:
            continue
        fig.add_trace(go.Scatter(
            x=dk["time"], y=dk["dual"], mode="markers", name=KIND_LABEL[kind],
            marker=dict(color=KIND_COLOR[kind], size=9, symbol="circle",
                        line=dict(color=C["surface"], width=1)),
            customdata=dk[["branch_var", "dual_gain"]],
            hovertemplate="%{customdata[0]} が改善<br>Δdual %{customdata[1]:.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="双対境界の改善と、効いた分枝(灰帯=停滞区間)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="求解時間 [s]", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="Dual bound", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=48, b=44), height=380, hovermode="closest",
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def fig_gain_by_kind(d) -> go.Figure:
    order = ["spatial", "integer", "binary"]
    g = gain_by_kind(d).set_index("kind")["dual_gain"]
    vals = [float(g.get(k, 0.0)) for k in order]
    fig = go.Figure(go.Bar(
        x=vals, y=[KIND_LABEL[k] for k in order], orientation="h",
        marker=dict(color=[KIND_COLOR[k] for k in order]),
        text=[f"{v:.1f}" for v in vals], textposition="outside",
        hovertemplate="%{y}: Δdual合計 %{x:.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="双対境界の改善量の帰属先(型別)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="Δdual 合計", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=110, r=48, t=44, b=40), height=220,
    )
    return fig


def fig_top_vars(d, top=10) -> go.Figure:
    g = gain_by_variable(d, top=top).iloc[::-1]  # 横棒は下から大きく
    fig = go.Figure(go.Bar(
        x=g["dual_gain"], y=g["branch_var"], orientation="h",
        marker=dict(color=[KIND_COLOR[k] for k in g["kind"]]),
        text=[f"{v:.1f}" for v in g["dual_gain"]], textposition="outside",
        customdata=g[["kind"]],
        hovertemplate="%{y} (%{customdata[0]})<br>Δdual合計 %{x:.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="双対境界を押し上げた分枝変数 上位(色=型)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="Δdual 合計", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=110, r=48, t=44, b=40), height=320,
    )
    return fig


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    ap.add_argument("--time", type=float, default=30.0)
    ap.add_argument("--gap", type=float, default=0.01)
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    model = module.build_model()
    print(f"solving {MODELS[args.model]} for attribution (time={args.time}s) ...")
    d, summary = solve_and_attribute(model, time_limit=args.time, gap_limit=args.gap)
    if d.empty or d["dual_gain"].sum() <= 0:
        print("双対境界の改善が記録されませんでした。--time を伸ばすか別モデルで試してください。")
        return

    stalls = detect_stalls(d)
    gk = gain_by_kind(d).set_index("kind")["dual_gain"]
    spatial_share = gk.get("spatial", 0.0) / d["dual_gain"].sum() * 100

    print(f"records={len(d)}  total Δdual={d['dual_gain'].sum():.2f}  "
          f"spatial share={spatial_share:.0f}%  stalls={len(stalls)}")

    tiles = [
        _tile("ステータス", summary["status"]),
        _tile("Gap", f"{summary['gap'] * 100:.2f}%" if summary["gap"] is not None else "—"),
        _tile("双対境界の総改善", f"{d['dual_gain'].sum():.1f}"),
        _tile("空間分枝の寄与率", f"{spatial_share:.0f}%"),
        _tile("停滞区間", f"{len(stalls)}個"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "attribution.html"
    d1 = fig_dual_attr(d, stalls).to_html(full_html=False, include_plotlyjs=True,
                                          config=dict(displayModeBar=False))
    d2 = fig_gain_by_kind(d).to_html(full_html=False, include_plotlyjs=False,
                                     config=dict(displayModeBar=False))
    d3 = fig_top_vars(d).to_html(full_html=False, include_plotlyjs=False,
                                 config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>双対境界改善の帰属</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1040px; margin:0 auto; padding:22px 16px; }}
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
</style></head><body><div class="wrap">
<h1>gap停滞と「効いた分枝変数」の紐付け(Phase 2.c)</h1>
<div class="sub">{MODELS[args.model]} — 双対境界の増分を直前の分枝変数に帰属させ、停滞と改善の因果を見る</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<div class="card">{d3}</div>
<p class="note">
双対境界(緑線)が上がるとgapが縮む。灰帯は境界がほぼ横ばいの<b>停滞区間</b>。改善点の色は
その改善に効いた分枝の型で、<b>青=空間分枝(連続変数)</b>・緑=整数分枝・桃=0-1分枝。
下段は改善量の帰属先。<b>空間分枝の寄与率が高いほど、非凸緩和の締めが最適性証明の律速</b>であり、
Phase 3では「その空間分枝が刺さる変数の境界タイト化・区分線形近似」が改善候補になる。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
