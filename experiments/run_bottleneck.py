"""線形制約のスラック(拘束)とIISの可視化

facility モデル(純粋線形MILP)で:
1. LP緩和のスラック=0 かつ 双対値(影の価格)が大きい制約 = 双対境界のボトルネック
2. 実行不能版のIIS(削除フィルタ法)= 最小の矛盾制約集合

実行: uv run python experiments/run_bottleneck.py
出力: results/bottleneck.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

_SAMPLES = Path(__file__).parent.parent / "samples"
# サンプルはカテゴリ別サブディレクトリにあるため、samples/ 本体と各サブディレクトリを path に載せる
for _p in [_SAMPLES, *(d for d in _SAMPLES.iterdir() if d.is_dir() and d.name != "__pycache__")]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from run_tree import C, FONT
from viz.bottleneck import analyze_slack

import minlpkit as mk
import facility

# 制約タイプ色(dataviz categorical 固定順)/ IISは status critical
TYPE_COLOR = {"demand": "#2a78d6", "capacity": "#008300", "open": "#e87ba4", "open_limit": "#e87ba4"}
CRITICAL = "#d03b3b"
MUTED = "#c3c2b7"


def _tcolor(ctype: str) -> str:
    return TYPE_COLOR.get(ctype, "#eda100")


def fig_bottleneck(df) -> go.Figure:
    # 拘束制約を |dual| 降順に(影の価格が大きいほど強いボトルネック)
    d = df[df["binding"]].copy()
    d["abs_dual"] = d["dual"].abs()
    d = d.sort_values("abs_dual", ascending=True)
    fig = go.Figure(go.Bar(
        x=d["abs_dual"], y=d["constraint"], orientation="h",
        marker=dict(color=[_tcolor(t) for t in d["ctype"]]),
        text=[f"{v:.2f}" for v in d["dual"]], textposition="outside",
        customdata=d[["slack", "dual"]],
        hovertemplate="%{y}<br>影の価格 %{customdata[1]:.2f}<br>スラック %{customdata[0]:.2g}<extra></extra>"))
    fig.update_layout(
        title=dict(text="拘束制約のボトルネック強度 = |影の価格|(スラック=0の制約のみ)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="|影の価格(双対値)|", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=110, r=56, t=44, b=40), height=360,
    )
    return fig


def fig_iis(all_cons, iis_set) -> go.Figure:
    # 全制約を並べ、IISメンバーを critical、非メンバーを muted で示す
    names = list(all_cons)
    in_iis = [n in iis_set for n in names]
    colors = [CRITICAL if m else MUTED for m in in_iis]
    fig = go.Figure(go.Bar(
        x=[1] * len(names), y=names, orientation="h",
        marker=dict(color=colors),
        text=["IIS(必須)" if m else "不要" for m in in_iis], textposition="inside",
        insidetextanchor="middle", textfont=dict(color="#fff", size=11),
        hovertemplate="%{y}: %{text}<extra></extra>"))
    fig.update_layout(
        title=dict(text=f"IIS(既約不整合部分系)— {len(iis_set)}/{len(names)}本が矛盾の核",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(visible=False, range=[0, 1.05]),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=110, r=20, t=44, b=20), height=360, bargap=0.35,
    )
    return fig


def main() -> None:
    print("analyzing slack/binding on feasible facility model ...")
    m = facility.build_model(infeasible=False)
    df = analyze_slack(m)
    n_bind = int(df["binding"].sum())
    top = df.loc[df["dual"].abs().idxmax()]
    print(f"linear constraints={len(df)}  binding={n_bind}  "
          f"strongest bottleneck: {top['constraint']} (影の価格 {top['dual']:.1f})")

    print("extracting IIS on infeasible facility model ...")
    # IIS(削除フィルタ)は minlpkit に一本化。通常の build_model を delete-by-name で縮約する
    res = mk.deletion_filter(lambda: facility.build_model(infeasible=True))
    all_cons = facility.constraint_names(infeasible=True)
    iis = sorted(res["core"])
    print(f"IIS ({len(iis)} constraints): {iis}")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "bottleneck.html"
    d1 = fig_bottleneck(df).to_html(full_html=False, include_plotlyjs=True,
                                    config=dict(displayModeBar=False))
    d2 = fig_iis(all_cons, set(iis)).to_html(full_html=False, include_plotlyjs=False,
                                             config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>線形制約のスラックとIIS</title>
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
<h1>線形制約のスラック(拘束)とIIS</h1>
<div class="sub">facility(純粋線形MILP)— ボトルネック制約の特定と、実行不能原因の最小核の抽出</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
<b>上図(スラック/影の価格)</b>: LP緩和でスラック=0の拘束制約のうち、影の価格(双対値)が大きいものほど
目的関数を強く制限する<b>ボトルネック</b>。<code>open_limit</code>(開設上限)が突出=これを緩めれば双対境界が最も動く。
これはノートの「スラックが0に張り付く制約=双対境界を押し下げる強固なボトルネック」の実装。
<br><b>下図(IIS)</b>: 実行不能版を削除フィルタ法(<code>mk.deletion_filter</code>)にかけ、「これ以上どれを外しても
不能でなくなる」最小の矛盾制約集合を抽出。赤=IIS必須。ここでは全capacity + 吊り上げた <code>demand_C4</code> +
<code>open_limit</code> が核で、他の需要制約は無関係と判定。IIS起点で修正ループへの入力に使える。
<br>※ <b>どれだけ緩めれば通るか</b>(弾性緩和スラック)や presolve当たり・診断ルール込みの実行不能診断は
<code>run_infeasibility.py</code>(<code>mk.diagnose_infeasibility</code>)を参照。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
