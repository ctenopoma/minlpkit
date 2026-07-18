"""静的診断(数値スケール/Big-M・制約-変数構造)の可視化 (Phase 2.c)

solve前にモデルから静的に取れる4つの診断を1画面に出す:
  A. 出所別の係数スケール(箱ひげ・対数)= 数値不安定/Big-Mの兆候
  B. 悪条件な線形制約(係数 max/min 比)上位
  C. 制約-変数の接続行列(RCM並べ替え)= ブロック対角性=分解適性
  D. 結合制約(多数の変数グループにまたがる制約)= 分解の境界

実行: uv run python experiments/run_static_diag.py --model uc     (Big-Mが顕著)
      uv run python experiments/run_static_diag.py --model plant  (ブロック構造が顕著)
出力: results/static_<model>.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.static_diag import (constraint_ratio, extract_coefficients, incidence,
                             linking_constraints, reorder_blocks, scale_summary)

MODELS = {"uc": "unit_commitment", "sched": "scheduling",
          "plant": "scheduling_plant", "facility": "facility"}
SRC_COLOR = {"制約係数": "#2a78d6", "RHS/LHS": "#008300",
             "目的係数": "#e87ba4", "変数境界": "#eda100"}
SEQ_BLUE = [[0.0, "#fcfcfb"], [1.0, "#2a78d6"]]
CRITICAL = "#d03b3b"


def fig_scale_box(df) -> go.Figure:
    fig = go.Figure()
    for src, color in SRC_COLOR.items():
        d = df[df["source"] == src]
        if d.empty:
            continue
        fig.add_trace(go.Box(y=d["magnitude"], name=src, marker=dict(color=color),
                             boxpoints="outliers", line=dict(width=1.5)))
    fig.update_layout(
        title=dict(text="係数の絶対値レンジ(出所別・対数)— 上に外れる点=Big-M/悪スケール",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        yaxis=dict(title="|値|(対数)", type="log", gridcolor=C["grid"],
                   linecolor=C["axis"], tickfont=dict(color=C["muted"])),
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=60, r=16, t=44, b=36), height=320,
    )
    return fig


def fig_ratio(model) -> go.Figure | None:
    d = constraint_ratio(model)
    if d.empty:
        return None
    d = d.head(12).iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["ratio"], y=d["constraint"], orientation="h", marker=dict(color="#2a78d6"),
        text=[f"{v:.0f}" for v in d["ratio"]], textposition="outside",
        hovertemplate="%{y}<br>max/min比 %{x:.1f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="悪条件な線形制約 上位(係数 max/min 比)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="max/min 比", type="log", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"])),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=90, r=48, t=44, b=36), height=340,
    )
    return fig


def fig_incidence(model) -> go.Figure:
    M, cn, vn = incidence(model)
    rp, cp, Mr = reorder_blocks(M)
    fig = go.Figure(go.Heatmap(
        z=Mr, colorscale=SEQ_BLUE, showscale=False, xgap=0, ygap=0,
        hoverinfo="skip"))
    fig.update_layout(
        title=dict(text=f"制約-変数 接続行列(RCM並べ替え {M.shape[0]}×{M.shape[1]})"
                        " — 対角ブロック=分解可能",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="変数(並べ替え後)", showticklabels=False, tickfont=dict(color=C["muted"])),
        yaxis=dict(title="制約(並べ替え後)", showticklabels=False, autorange="reversed"),
        margin=dict(l=60, r=16, t=44, b=36), height=420,
    )
    return fig


def fig_linking(model) -> go.Figure:
    d = linking_constraints(model).head(12).iloc[::-1]
    maxg = d["n_groups"].max()
    colors = [CRITICAL if g == maxg else "#2a78d6" for g in d["n_groups"]]
    fig = go.Figure(go.Bar(
        x=d["n_groups"], y=d["constraint"], orientation="h", marker=dict(color=colors),
        text=d["n_groups"], textposition="outside",
        customdata=d[["n_vars", "groups"]],
        hovertemplate="%{y}<br>またがるグループ数 %{x}<br>変数 %{customdata[0]}<extra></extra>"))
    fig.update_layout(
        title=dict(text="結合制約 = またがる変数グループ数(赤=最多=分解の境界)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="またがるグループ数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=90, r=48, t=44, b=36), height=340,
    )
    return fig


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="uc")
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    model = module.build_model()

    df = extract_coefficients(model)
    s = scale_summary(df)
    print(f"[{args.model}] coeff={len(df)}  |min|={s['min']:.3g}  |max|={s['max']:.3g}  "
          f"ratio={s['ratio']:.3g}  Big-M候補={len(s['bigm'])}")
    lk = linking_constraints(model)
    print(f"top linking: {lk.iloc[0]['constraint']} spans {lk.iloc[0]['n_groups']} groups")

    figs = [fig_scale_box(df)]
    fr = fig_ratio(model)
    if fr is not None:
        figs.append(fr)
    figs += [fig_incidence(model), fig_linking(model)]

    ratio_txt = f"{s['ratio']:.0f}" if s["ratio"] is not None else "—"
    bigm_txt = ", ".join(f"{b['name']}={b['magnitude']:.0f}" for b in s["bigm"][:3]) or "なし"
    tiles = [
        _tile("係数 |min|", f"{s['min']:.3g}" if s["min"] is not None else "—"),
        _tile("係数 |max|", f"{s['max']:.3g}" if s["max"] is not None else "—"),
        _tile("max/min 比", ratio_txt),
        _tile("Big-M候補数", len(s["bigm"])),
        _tile("結合制約(最多グループ)", f"{lk.iloc[0]['n_groups']}"),
    ]

    chart_html = "".join(
        '<div class="card">'
        + f.to_html(full_html=False, include_plotlyjs=(i == 0), config=dict(displayModeBar=False))
        + "</div>" for i, f in enumerate(figs))

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / f"static_{args.model}.html"
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>静的診断 {args.model}</title>
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
<h1>静的診断: 数値スケールと構造(Phase 2.c)</h1>
<div class="sub">{MODELS[args.model]} — solve前にモデルから取れる数値健全性・分解適性。Big-M候補: {bigm_txt}</div>
<div class="tiles">{''.join(tiles)}</div>
{chart_html}
<p class="note">
<b>係数スケール</b>: 出所別の絶対値レンジ。max/min比が大きい・上に外れる点がある = 数値不安定/Big-Mの兆候。
Phase 3の「Big-M排除(Indicator/SOS)・スケーリング」の判断材料。
<b>接続行列</b>: RCMで並べ替えると対角ブロックが浮く=その単位で<b>分解可能</b>。
<b>結合制約</b>(赤)は多数の変数グループをまたぐ制約で、これがベンダーズ/Dantzig-Wolfe分解の境界になる。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
