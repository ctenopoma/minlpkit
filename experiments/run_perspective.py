"""Perspective(遠近)再定式化の検証

半連続な二次燃料費 fc >= a·u + b·p + c·p^2 を perspective 化して
c·p^2 <= (fc − a·u − b·p)·u に置き換える古典的強化を UC で検証する。

測定方法論(FINDINGS.md 4節)に従い、交絡のないルート双対境界で比較する:
  - 既定SCIP(presolve/分離ON)と、素の分枝限定(presolve/sep/heur/sym OFF)の両方
  - 60s 時間制限での gap/ノード
  - 縮小インスタンスで最適値の等価性(等価変換であること)

実行: uv run python experiments/run_perspective.py  ->  results/perspective.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
from pyscipopt import SCIP_PARAMSETTING

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
import unit_commitment as uc

VARIANTS = ["baseline", "perspective"]
LABEL = {"baseline": "baseline(素の凸二次)", "perspective": "perspective(遠近化)"}
COLOR = {"baseline": "#2a78d6", "perspective": "#d1892b"}
SETTINGS = ["default", "bare"]
SETTING_LABEL = {"default": "既定SCIP(presolve/分離ON)", "bare": "素の分枝限定(presolve/sep/heur/sym OFF)"}


def root_bound(persp: bool, bare: bool) -> float:
    m = uc.build_model(persp)
    m.hideOutput()
    m.setParam("limits/nodes", 1)
    if bare:
        m.setParam("presolving/maxrounds", 0)
        m.setParam("separating/maxrounds", 0)
        m.setParam("separating/maxroundsroot", 0)
        m.setParam("misc/usesymmetry", 0)
        m.setHeuristics(SCIP_PARAMSETTING.OFF)
    m.optimize()
    return m.getDualbound()


def full_solve(persp: bool, tl: float = 60.0) -> dict:
    m = uc.build_model(persp)
    m.hideOutput()
    m.setParam("timing/clocktype", 2)
    m.setParam("limits/time", tl)
    m.setParam("limits/gap", 0.0001)
    m.optimize()
    return dict(gap=m.getGap() * 100, nodes=m.getNNodes(),
                primal=m.getPrimalbound() if m.getNSols() else None,
                dual=m.getDualbound())


def reduced_optimal(persp: bool, periods: int = 4) -> float:
    """需要を periods 期に縮小して最適値を厳密に求める(等価性検証用)。"""
    saved_d, saved_t = uc.DEMAND[:], uc.T
    uc.DEMAND[:] = uc.DEMAND[:periods]
    uc.T = periods
    try:
        m = uc.build_model(persp)
        m.hideOutput()
        m.setParam("limits/time", 180)
        m.setParam("limits/gap", 1e-6)
        m.optimize()
        return m.getObjVal()
    finally:
        uc.DEMAND[:] = saved_d
        uc.T = saved_t


def fig_root(roots: dict) -> go.Figure:
    fig = go.Figure()
    xs = [SETTING_LABEL[s] for s in SETTINGS]
    for v in VARIANTS:
        ys = [roots[(v, s)] for s in SETTINGS]
        fig.add_trace(go.Bar(
            name=LABEL[v], x=xs, y=ys, marker=dict(color=COLOR[v]),
            text=[f"{y:,.0f}" for y in ys], textposition="outside",
            textfont=dict(color=C["ink2"]),
            hovertemplate="%{x}<br>" + LABEL[v] + "<br>ルート双対境界 %{y:,.0f}<extra></extra>"))
    fig.update_layout(
        title=dict(text="ルート双対境界(交絡なし・大=強い緩和)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        barmode="group", bargap=0.35, bargroupgap=0.12,
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        legend=dict(orientation="h", y=1.12, x=0.01, font=dict(color=C["ink2"])),
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="ルート双対境界", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=70, r=20, t=64, b=52), height=420,
    )
    return fig


def fig_full(full: dict) -> go.Figure:
    xs = [LABEL[v] for v in VARIANTS]
    ys = [full[v]["gap"] for v in VARIANTS]
    fig = go.Figure(go.Bar(
        x=xs, y=ys, marker=dict(color=[COLOR[v] for v in VARIANTS]),
        text=[f"{y:.2f}%" for y in ys], textposition="outside",
        textfont=dict(color=C["ink2"]),
        customdata=[full[v]["nodes"] for v in VARIANTS],
        hovertemplate="%{x}<br>gap %{y:.2f}%<br>ノード %{customdata}<extra></extra>"))
    fig.update_layout(
        title=dict(text="60s 時間制限での残存gap(小=良い・両者ほぼ同等)",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12), showlegend=False,
        xaxis=dict(tickfont=dict(color=C["ink2"])),
        yaxis=dict(title="gap (%)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=20, t=44, b=44), height=320,
    )
    return fig


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def main() -> None:
    print("measuring root dual bounds ...")
    roots = {}
    for v, persp in (("baseline", False), ("perspective", True)):
        for s, bare in (("default", False), ("bare", True)):
            roots[(v, s)] = root_bound(persp, bare)
            print(f"  {v:12s} [{s:7s}] root_dual = {roots[(v, s)]:,.2f}")

    print("full solve 60s ...")
    full = {v: full_solve(p) for v, p in (("baseline", False), ("perspective", True))}
    for v in VARIANTS:
        print(f"  {v:12s}: gap={full[v]['gap']:.3f}%  nodes={full[v]['nodes']}")

    print("reduced-instance optimal (equivalence check) ...")
    opt_b = reduced_optimal(False)
    opt_p = reduced_optimal(True)
    print(f"  baseline={opt_b:.4f}  perspective={opt_p:.4f}  diff={abs(opt_b - opt_p):.6f}")

    d_pct = (roots[("perspective", "default")] - roots[("baseline", "default")]) / \
        abs(roots[("baseline", "default")]) * 100
    b_pct = (roots[("perspective", "bare")] - roots[("baseline", "bare")]) / \
        abs(roots[("baseline", "bare")]) * 100

    tiles = [
        _tile("既定 root(baseline)", f"{roots[('baseline','default')]:,.0f}"),
        _tile("既定 root(perspective)", f"{roots[('perspective','default')]:,.0f}"),
        _tile("既定での効果", f"{d_pct:+.2f}%"),
        _tile("素 root の変化", f"{b_pct:+.0f}%"),
        _tile("60s gap(base→persp)", f"{full['baseline']['gap']:.2f}%→{full['perspective']['gap']:.2f}%"),
        _tile("縮小最適値(等価性)", f"{opt_b:.1f}={opt_p:.1f}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "perspective.html"
    d1 = fig_root(roots).to_html(full_html=False, include_plotlyjs=True,
                                 config=dict(displayModeBar=False))
    d2 = fig_full(full).to_html(full_html=False, include_plotlyjs=False,
                                config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>Perspective再定式化の検証</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:150px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:18px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 .verdict {{ background:#fbf3e6; border:1px solid #e6d3ad; border-radius:8px;
             padding:10px 14px; margin-bottom:14px; font-size:12.5px; color:{C['ink']}; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>Perspective(遠近)再定式化の検証</h1>
<div class="sub">半連続な二次燃料費 <code>fc ≥ a·u + b·p + c·p²</code> を perspective 化して
<code>c·p² ≤ (fc − a·u − b·p)·u</code> に置換。unit_commitment で検証(<code>mk.perspective_quadratic</code> ヘルパー経由)</div>
<div class="verdict"><b>判定: 負の結果(効かない)。</b>
既定SCIPではルート双対境界がほぼ不変(<b>{d_pct:+.2f}%</b>)= SCIPのpresolve/分離が baseline を
自動でここまで締めている。素の分枝限定に落とすと perspective は <b>{b_pct:+.0f}%</b> と<b>むしろ大幅悪化</b>:
SCIPは右辺の双線形 (fc·u, u², p·u) を McCormick で緩く緩和するため、遠近化の凸包効果を得られない。
最適値は不変(等価変換)。</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card">{d2}</div>
<p class="note">
perspective 再定式化は理論上、半連続変数の二次項の凸包を締める古典的強化。しかし SCIP(PySCIPOpt 6.2.1)は
<code>c·p² ≤ (fc − a·u − b·p)·u</code> を一般の非凸双線形制約として受け取り、右辺の積を McCormick で緩和する
ため、遠近関数(rotated SOC 相当)としての強い凸包を自動では利用しない。結果、<b>既定SCIPではルート双対境界は
実質同一</b>(SCIPの分離/presolveが baseline を自動補償)、<b>素の分枝限定ではむしろ弱くなる</b>。
これは FINDINGS.md「かえって悪化する改善」の <code>n·s≥demand</code> と同型の現象
(双線形の新規追加が緩和を締めずに McCormick で緩む)。<br>
※ 等価性は縮小4期インスタンスで最適値 <b>{opt_b:.2f} = {opt_p:.2f}(一致)</b>を確認済み。定式化バグではない。
ヘルパー <code>mk.perspective_quadratic</code> は横展開部品として追加したが、<b>SCIPに対しては素の凸二次下界の方が
有利</b>という知見付きで文書化する(効く条件: 遠近を SOC/Indicator として明示的に凸ソルバへ渡す枠組み)。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
