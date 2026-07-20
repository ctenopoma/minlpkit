"""実行不可能モデルの犯人制約を特定して可視化する

弾性緩和(全線形制約にスラックを足しΣを最小化)で「どの制約をどれだけ緩めれば通るか」を、
削除フィルタ(1本ずつ外して解き直す)で「これ以上減らせない矛盾の核=IIS」を求める。
横棒の長さ=必要な緩和量(スラック)、色=IIS核の当事者か。人が怪しい制約をOn/Off・緩和して
原因を探る作業の自動化。

実行: uv run python experiments/run_infeasibility.py --model supply
出力: results/infeasibility.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples" / "others"))

from run_tree import C, FONT  # 共通デザイントークン

import minlpkit as mk

MODELS = {"supply": "infeasible_supply_plan"}
# status: 矛盾の核=serious(warm red)、非核=muted gray。status色は識別子(緑青等)と別系統
CORE_COLOR = "#cf5340"
NONCORE_COLOR = C["muted"]


def fig_slack_bar(elastic, core: set[str]) -> go.Figure:
    """線形制約ごとの弾性スラック横棒 + IIS核マーカー。

    2つの独立した信号を1枚に:棒の長さ = 弾性緩和で必要な緩和量(どれだけ緩めれば通るか)、
    左ガターの赤ダイヤ = 削除フィルタが返したIIS核の当事者。核メンバーはスラックが0でも
    (核は「どれか1本緩めれば通る」連立の矛盾で最小コスト解が別の1本に寄るため)ガターの
    マーカーで必ず可視になる。棒の色も核=赤/非核=グレーで冗長に符号化する。
    """
    df = elastic.dropna(subset=["slack"]).copy()
    df["in_core"] = df["constraint"].isin(core)
    # 核を上に、その中でスラック降順。横棒は下から上に描かれるので昇順に積む
    df = df.sort_values(["in_core", "slack"], ascending=[True, True])

    colors = [CORE_COLOR if c else NONCORE_COLOR for c in df["in_core"]]
    labels = [f"{v:.1f}" if v > 1e-6 else "0" for v in df["slack"]]
    max_slack = float(df["slack"].max()) if not df.empty else 1.0
    max_slack = max_slack if max_slack > 0 else 1.0
    gutter = max_slack * 0.045   # 左ガターの核マーカー位置

    fig = go.Figure()
    # スラック棒(magnitude)。凡例には出さない(色の意味は下の核マーカー凡例と注記で説明)
    fig.add_trace(go.Bar(
        x=df["slack"], y=df["constraint"], orientation="h", showlegend=False,
        marker=dict(color=colors, line=dict(width=0)),
        text=labels, textposition="outside", cliponaxis=False,
        customdata=list(zip(df["sense"], df["in_core"])),
        hovertemplate="%{y}(%{customdata[0]})<br>必要な緩和量 %{x:.2f}"
                      "<br>IIS核: %{customdata[1]}<extra></extra>"))
    # IIS核マーカー(左ガターの赤ダイヤ)。スラック0の核メンバーもここで必ず可視になる
    core_df = df[df["in_core"]]
    fig.add_trace(go.Scatter(
        x=[-gutter] * len(core_df), y=core_df["constraint"], mode="markers",
        name="IIS核(矛盾の当事者)", marker=dict(symbol="diamond", color=CORE_COLOR, size=10),
        hovertemplate="%{y}: IIS核<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=C["axis"], width=1))
    fig.update_layout(
        title=dict(text="弾性緩和スラック(棒=緩める必要量) + IIS核(◆=矛盾の当事者)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="必要な緩和量(スラック)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False,
                   range=[-gutter * 2.2, max_slack * 1.18]),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        legend=dict(orientation="h", y=1.07, x=0.99, xanchor="right",
                    font=dict(color=C["ink2"], size=11), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=110, r=54, t=64, b=44), height=360,
    )
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="supply")
    ap.add_argument("--time-limit", type=float, default=10.0)
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    build_fn = module.build_model

    print(f"diagnosing infeasibility for {MODELS[args.model]} ...")
    res = mk.diagnose_infeasibility(build_fn, time_limit=args.time_limit)
    if not res["infeasible"]:
        print(f"このモデルは実行不可能ではない(status={res['status']})。診断対象外。")
        return

    core = set(res["iis_core"])
    print(f"presolve証明={res['presolve_infeasible']}  IIS核={sorted(core)}  ({res['iis_note']})")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "infeasibility.html"
    fig = fig_slack_bar(res["elastic"], core)
    plot = fig.to_html(full_html=False, include_plotlyjs=True,
                       config=dict(displayModeBar=False))

    core_chips = "".join(f'<span class="chip core">{c}</span>' for c in sorted(core))
    pre = "presolveの境界タイト化だけで矛盾を証明済み" if res["presolve_infeasible"] \
        else "presolveでは証明できず本探索で判定"
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>実行不可能の犯人特定</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1040px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .pad {{ padding:14px 16px; }}
 .kpi {{ font-size:13px; color:{C['ink2']}; line-height:1.9; }}
 .kpi b {{ color:{C['ink']}; }}
 .chip {{ display:inline-block; font-size:12px; padding:2px 9px; border-radius:12px;
          margin:2px 4px 2px 0; }}
 .chip.core {{ background:rgba(207,83,64,0.12); color:#a23a29;
              border:1px solid rgba(207,83,64,0.35); }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>実行不可能(infeasible)の犯人制約を特定</h1>
<div class="sub">{MODELS[args.model]} — 弾性緩和(必要な緩和量)+ 削除フィルタ(IIS核)</div>
<div class="card"><div class="pad kpi">
 全 <b>{res['n_conss']}</b> 本の制約のうち、これ以上減らせない矛盾の核(IIS)は
 <b>{len(core)}</b> 本 &nbsp;→&nbsp; {core_chips}<br>
 solve前の当たり: {pre}。
</div></div>
<div class="card">{plot}</div>
<div class="card"><div class="pad note">
<b>読み方.</b> 横棒の長さ = その制約を実行可能にするために<b>緩める必要がある量</b>
(弾性緩和のスラック)。赤 = <b>IIS核の当事者</b>(削除フィルタが「1本ずつ外して解き直し、
外しても実行不可能なら犯人でない→捨てる」を繰り返し、最後に残った矛盾の核)。核メンバーでも
スラックが0のことがある(核は<b>どれか1本を緩めれば通る</b>連立の矛盾なので、緩和の最小コスト解が
別の1本に寄るため)。<br>
<b>直し方.</b> 赤い制約のどれか1本を緩める/RHSを見直せば実行可能になる。ここでは
<code>cap_total</code>(能力100)と <code>contract_A/B/C</code>(各最低40=合計120)が
矛盾しており、能力を上げるか契約を1本落とせば通る。<br>
API: <code>mk.diagnose_infeasibility(build_fn)</code> /
<code>mk.elastic_filter(build_fn)</code> / <code>mk.deletion_filter(build_fn)</code>。
</div></div>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
