"""Phase 6: 行列条件数 κ(A) 診断(Model Analyzer の核心)

ノートの Gurobi Model Analyzer が指す条件数 κ(A)=‖A‖·‖A⁻¹‖ を実装。
- 静的 κ(A): 線形制約の係数行列のSVDから(solve前)。定式化の悪条件を検出
- SCIP LP基底 κ: getCondition(solve後)。実際の数値不安定度
緩いBig-M vs tight で κ(A) が激変することを示す。

実行: uv run python experiments/run_condition.py  ->  results/condition.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.static_diag import matrix_condition, scip_basis_condition

import fixed_charge as fc
import facility as fac
import unit_commitment as uc
import scheduling_plant as sp

MODELS = [
    ("緩いBig-M\n(fixed_charge)", lambda: fc.build_model("loose")),
    ("tight Big-M\n(fixed_charge)", lambda: fc.build_model("tight")),
    ("facility", lambda: fac.build_model()),
    ("unit_commitment", lambda: uc.build_model()),
]
# 悪条件のしきい値(この辺を超えると数値的に要注意)
WARN = 1e7


def fig_condition(names, kappas, scip_ks) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names, y=kappas, name="静的 κ(A)(係数行列)",
        marker=dict(color="#2a78d6"),
        text=[f"{k:.1e}" if k else "—" for k in kappas], textposition="outside",
        hovertemplate="%{x}<br>κ(A)=%{y:.2e}<extra></extra>"))
    fig.add_trace(go.Bar(
        x=names, y=scip_ks, name="SCIP LP基底 κ(getCondition)",
        marker=dict(color="#008300"),
        text=[f"{k:.1e}" if k else "—" for k in scip_ks], textposition="outside",
        hovertemplate="%{x}<br>基底κ=%{y:.2e}<extra></extra>"))
    fig.add_hline(y=WARN, line=dict(color="#d03b3b", width=2, dash="dash"),
                  annotation_text="数値的に要注意 (1e7)", annotation_position="top left",
                  annotation_font=dict(color="#d03b3b", size=11))
    fig.update_layout(
        title=dict(text="条件数 κ(A) 診断 — 大きいほど悪条件(丸め誤差でソルバーが迷走)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), barmode="group",
        xaxis=dict(tickfont=dict(color=C["ink2"], size=11)),
        yaxis=dict(title="条件数(対数)", type="log", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"])),
        margin=dict(l=60, r=16, t=48, b=54), height=420,
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def main() -> None:
    print("computing condition numbers ...")
    names, kappas, scip_ks = [], [], []
    for label, build in MODELS:
        mc = matrix_condition(build())
        sk = scip_basis_condition(build())
        names.append(label.replace("\n", " "))
        kappas.append(mc["kappa"])
        scip_ks.append(sk)
        print(f"  {label.replace(chr(10),' '):28s}: κ(A)={mc['kappa']:.3e}  SCIP基底κ={sk}")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_condition([n.replace(" (", "<br>(") for n in names], kappas, scip_ks)
    fig.write_image(str(outdir / "_cond.png"), width=950, height=420, scale=1)  # 検証用
    d1 = fig.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))

    loose_k, tight_k = kappas[0], kappas[1]
    uc_basis = scip_ks[3]
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>条件数 κ(A) 診断</title>
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
<h1>条件数 κ(A) 診断(Phase 6 / Model Analyzer の核心)</h1>
<div class="sub">係数行列の条件数 κ(A)=‖A‖·‖A⁻¹‖ を静的(SVD)とSCIP LP基底(getCondition)で計測</div>
<div class="card">{d1}</div>
<p class="note">
ノートの Gurobi Model Analyzer が指す条件数を実装。<b>静的 κ(A)</b>(青)は係数行列のSVDから solve前に、
<b>SCIP LP基底 κ</b>(緑)は最適基底の実際の条件数を getCondition から得る。
<b>緩いBig-Mは κ(A)={loose_k:.1e} と悪条件、tight化で {tight_k:.0f} に激減</b>(定式化が数値健全性を左右する)。
<b>unit_commitment はLP基底 κ≈{uc_basis:.1e} と極端に大きく、実際に数値不安定リスク</b>がある
(SCIP 10 の厳密有理MILPモードが効く領域)。従来の係数max/min比の代用でなく、真の κ(A) で診断できるようになった。
</p>
</div></body></html>"""
    (outdir / "condition.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'condition.html'}")


if __name__ == "__main__":
    main()
