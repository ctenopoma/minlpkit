"""Phase 4: SCIPパラメータ自動チューニング(Optuna)の効果検証

線形化版plantで、固定時間の双対境界を最大化するSCIPパラメータをOptunaで探索。
SCIPが自動ではやらない問題クラス特化のメタ最適化。

実行: uv run python experiments/run_tune.py  ->  results/tune.html
"""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.tune import tune

N_TRIALS = 16
TIME_LIMIT = 7.0


def fig_history(trials, default) -> go.Figure:
    xs = [t["number"] for t in trials]
    ys = [t["value"] for t in trials]
    best = []
    cur = -1e18
    for y in ys:
        cur = max(cur, y)
        best.append(cur)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode="markers", name="各試行",
        marker=dict(color="#86b6ef", size=8, line=dict(color=C["surface"], width=1)),
        hovertemplate="試行%{x}<br>dual %{y:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=xs, y=best, mode="lines", name="ベスト更新",
        line=dict(color="#2a78d6", width=2, shape="hv"),
        hovertemplate="ベスト %{y:.2f}<extra></extra>"))
    fig.add_hline(y=default, line=dict(color="#d03b3b", width=2, dash="dash"),
                  annotation_text=f"デフォルト {default:.1f}", annotation_position="bottom right",
                  annotation_font=dict(color=C["ink2"], size=11))
    fig.update_layout(
        title=dict(text="Optuna探索: 固定時間の双対境界(高い=良い)",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(title="試行", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), dtick=2, zeroline=False),
        yaxis=dict(title="双対境界", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=60, r=16, t=48, b=44), height=380, hovermode="closest",
        legend=dict(orientation="h", y=1.0, yanchor="bottom", x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"])),
    )
    return fig


def _tile(label, value, good=False):
    color = "#0ca30c" if good else C["ink"]
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value" style="color:{color}">{value}</div></div>')


def main() -> None:
    print(f"tuning SCIP params on linearized plant ({N_TRIALS} trials, {TIME_LIMIT}s each) ...")
    res = tune(n_trials=N_TRIALS, time_limit=TIME_LIMIT)
    gain = (res["best_dual"] - res["default_dual"]) / abs(res["default_dual"]) * 100
    bp = res["best_params"]
    print(f"default={res['default_dual']:.2f} best={res['best_dual']:.2f} (+{gain:.1f}%)")
    print(f"best params: {bp}")

    tiles = [
        _tile("デフォルト双対境界", f"{res['default_dual']:.1f}"),
        _tile("チューニング後", f"{res['best_dual']:.1f}", good=True),
        _tile("改善", f"+{gain:.1f}%", good=True),
        _tile("試行回数", f"{len(res['trials'])}"),
    ]
    param_rows = "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in bp.items())

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_history(res["trials"], res["default_dual"])
    fig.write_image(str(outdir / "_tune.png"), width=900, height=380, scale=1)  # 検証用
    d1 = fig.to_html(full_html=False, include_plotlyjs=True, config=dict(displayModeBar=False))
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>パラメータチューニング</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:1000px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:130px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:19px; font-variant-numeric:tabular-nums; }}
 .card {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; margin-bottom:12px; overflow:hidden; }}
 table {{ border-collapse:collapse; font-size:12.5px; margin:0 4px; }}
 td {{ padding:5px 14px; border-bottom:1px solid {C['grid']}; }}
 td:first-child {{ color:{C['muted']}; }}
 .note {{ color:{C['ink2']}; font-size:12px; line-height:1.7; }}
</style></head><body><div class="wrap">
<h1>SCIPパラメータ自動チューニング(Phase 4)</h1>
<div class="sub">線形化版plant — Optunaで固定{TIME_LIMIT:.0f}sの双対境界を最大化する設定を探索</div>
<div class="tiles">{''.join(tiles)}</div>
<div class="card">{d1}</div>
<div class="card"><table><tbody>{param_rows}</tbody></table></div>
<p class="note">
分離(separating)・ヒューリスティクス・presolve・分岐規則の強度をOptunaで探索。
<b>デフォルト {res['default_dual']:.1f} → 最良 {res['best_dual']:.1f}(+{gain:.1f}%)</b>。
最良は <code>separating=fast, heuristics=fast, branching=mostinf</code> 系
= この問題クラスでは<b>カット/ヒューリスティクスを軽くして分岐で双対境界を押す</b>方が固定時間で有利。
SCIPが自動ではやらない、問題クラスへの設定特化(メタ最適化)。運用では代表インスタンス群で
チューニングして本番設定を固定する。
</p>
</div></body></html>"""
    (outdir / "tune.html").write_text(html, encoding="utf-8")
    print(f"wrote {outdir / 'tune.html'}")


if __name__ == "__main__":
    main()
