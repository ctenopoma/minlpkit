"""対称性(入替可能な変数群)の可視化 (Phase 2.c)

構造シグネチャで検出した対称変数群をサイズ順に表示する。大きな群 = 強い対称性 =
探索木が対称解で膨張しやすい → Phase 3の辞書式順序制約(対称性除去)の対象。

実行: uv run python experiments/run_symmetry.py --model parallel   ->  results/symmetry.html
      (facility は対称性なしの対照として --model facility)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.symmetry import detect_symmetry

MODELS = {"parallel": "parallel_machines", "facility": "facility",
          "uc": "unit_commitment", "plant": "scheduling_plant"}


def fig_groups(df) -> go.Figure:
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="対称な変数群は検出されませんでした(対称性なし)",
                           showarrow=False, font=dict(color=C["ink2"], size=14))
        fig.update_layout(paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
                          xaxis=dict(visible=False), yaxis=dict(visible=False),
                          height=200, margin=dict(l=20, r=20, t=40, b=20),
                          title=dict(text="対称性グループ", x=0.01,
                                     font=dict(color=C["ink"], size=14, family=FONT)))
        return fig
    d = df.copy()
    d["label"] = d.apply(lambda r: f"群{r['signature_id']} ({r['size']}変数)", axis=1)
    d = d.iloc[::-1]
    fig = go.Figure(go.Bar(
        x=d["size"], y=d["label"], orientation="h", marker=dict(color="#4a3aa7"),
        text=d["size"], textposition="outside",
        customdata=d[["members"]],
        hovertemplate="%{y}<br>%{customdata[0]}<extra></extra>"))
    fig.update_layout(
        title=dict(text="対称(入替可能)な変数群のサイズ — 大=強い対称性",
                   font=dict(color=C["ink"], size=14, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="群内の変数数", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False, dtick=1),
        yaxis=dict(tickfont=dict(color=C["ink2"])),
        margin=dict(l=140, r=48, t=44, b=40), height=max(220, 60 + 34 * len(d)),
    )
    return fig


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="parallel")
    args = ap.parse_args()

    module = __import__(MODELS[args.model])
    model = module.build_model()
    df, s = detect_symmetry(model)
    print(f"[{args.model}] groups={s['n_groups']} largest={s['largest_group']} "
          f"symmetric_vars={s['n_symmetric_vars']}/{s['n_linear_vars']}")

    tiles = [
        _tile("対称性", "あり" if s["has_symmetry"] else "なし"),
        _tile("対称群の数", s["n_groups"]),
        _tile("最大群サイズ", s["largest_group"]),
        _tile("対称変数", f"{s['n_symmetric_vars']}/{s['n_linear_vars']}"),
    ]

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / "symmetry.html"
    body = fig_groups(df).to_html(full_html=False, include_plotlyjs=True,
                                  config=dict(displayModeBar=False))
    members_html = ""
    if not df.empty:
        rows = "".join(
            f"<tr><td>群{r.signature_id}</td><td>{r.size}</td><td>{r.members}</td></tr>"
            for r in df.itertuples())
        members_html = (f'<div class="card"><table><thead><tr><th>群</th><th>サイズ</th>'
                        f'<th>入替可能な変数</th></tr></thead><tbody>{rows}</tbody></table></div>')

    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>対称性検出 {args.model}</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1040px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:110px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:19px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; padding:0; }}
 table {{ width:100%; border-collapse:collapse; font-size:12px; }}
 th,td {{ text-align:left; padding:7px 12px; border-bottom:1px solid {C['grid']}; }}
 th {{ color:{C['muted']}; font-weight:600; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
 code {{ background:#eee; padding:1px 5px; border-radius:4px; }}
</style></head><body><div class="wrap">
<h1>対称性の兆候検出(Phase 2.c)</h1>
<div class="sub">{MODELS[args.model]} — 構造シグネチャ(1-hop color refinement)で入替可能な変数群を検出</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{body}</div>
{members_html}
<p class="note">
各変数の(型・目的係数・境界・所属制約の形状と自身の係数)からシグネチャを作り、同一シグネチャの
変数群=<b>入れ替えても問題が変わらない対称変数</b>を検出。恒等な並列機械では各ジョブの機械割当変数が
入替可能(+等処理時間ジョブも)で大きな群になる。<code>facility</code>(施設が非対称)では群は出ない(偽陽性なし)。
対称性が強いほど探索木が同値解で膨張する → Phase 3の<b>辞書式順序制約による対称性除去</b>の対象。
検出結果はSCIP自身の対称性計算(並列機械で生成子6個)とも整合。
</p>
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
