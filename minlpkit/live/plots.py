"""収束ログのPlotlyダッシュボード生成 (Phase 1)

dataviz スキルの参照パレット(検証済み)を使用。ローカル分析用HTMLのため
ライトテーマに固定する。1チャート1軸、系列色は固定順(slot1=青, slot2=緑)。

このモジュールは plotly を必要とする(`minlpkit[viz]` extra)。
"""

from __future__ import annotations

import pandas as pd

try:
    import plotly.graph_objects as go
except ModuleNotFoundError as _e:  # pragma: no cover - extras 未導入時の案内
    raise ModuleNotFoundError(
        "minlpkit.live のダッシュボード生成には plotly が必要です。"
        '`uv add "minlpkit[viz]"` で導入してください。'
    ) from _e

# 参照パレット (dataviz references/palette.md, light)
C = dict(
    surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
    muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
    s1="#2a78d6",  # slot1 blue  → primal
    s2="#008300",  # slot2 green → dual
)
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def _base_layout(title: str, ytitle: str, xtitle: str = "求解時間 [s]") -> go.Layout:
    ax = dict(
        gridcolor=C["grid"], linecolor=C["axis"], tickfont=dict(color=C["muted"], size=11),
        title_font=dict(color=C["ink2"], size=12), zeroline=False,
    )
    return go.Layout(
        title=dict(text=title, font=dict(color=C["ink"], size=15, family=FONT), x=0.01),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=12),
        xaxis=dict(ax, title=xtitle), yaxis=dict(ax, title=ytitle),
        margin=dict(l=60, r=20, t=48, b=48), height=380,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"]), bgcolor="rgba(0,0,0,0)"),
    )


def fig_bounds(df: pd.DataFrame) -> go.Figure:
    """primal / dual bound の推移(暫定解マーカー付き)を描く。"""
    fig = go.Figure(layout=_base_layout("Primal / Dual bound の推移", "目的関数値"))
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["dual"], name="Dual bound", mode="lines",
        line=dict(color=C["s2"], width=2, shape="hv"),
        hovertemplate="dual %{y:,.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=df["time"], y=df["primal"], name="Primal bound", mode="lines",
        line=dict(color=C["s1"], width=2, shape="hv"),
        hovertemplate="primal %{y:,.1f}<extra></extra>"))
    inc = df[df["event"] == "incumbent"]
    if not inc.empty:
        fig.add_trace(go.Scatter(
            x=inc["time"], y=inc["primal"], name="暫定解の更新", mode="markers",
            marker=dict(color=C["s1"], size=9, symbol="diamond",
                        line=dict(color=C["surface"], width=2)),
            customdata=inc[["nodes", "nsols"]],
            hovertemplate="暫定解 %{y:,.1f}<br>ノード %{customdata[0]:,} / 第%{customdata[1]}解<extra></extra>"))
    return fig


def fig_gap(df: pd.DataFrame) -> go.Figure:
    """gap の推移を対数軸で描く。"""
    fig = go.Figure(layout=_base_layout("Gap の推移(対数)", "gap [%]"))
    fig.update_layout(yaxis_type="log", showlegend=False)
    d = df.dropna(subset=["gap"])
    d = d[d["gap"] > 0]
    fig.add_trace(go.Scatter(
        x=d["time"], y=d["gap"] * 100, mode="lines",
        line=dict(color=C["s1"], width=2, shape="hv"),
        hovertemplate="gap %{y:.2f}%<extra></extra>"))
    return fig


def fig_primal_gap(pg: pd.DataFrame) -> go.Figure:
    """primal gap p(t)(最終解基準)の推移を描く。"""
    fig = go.Figure(layout=_base_layout("Primal gap p(t)(最終解基準)", "primal gap [%]"))
    fig.update_layout(showlegend=False)
    fig.add_trace(go.Scatter(
        x=pg["time"], y=pg["pgap"] * 100, mode="lines", fill="tozeroy",
        line=dict(color=C["s1"], width=2, shape="hv"),
        fillcolor="rgba(42,120,214,0.10)",
        hovertemplate="p(t) %{y:.2f}%<extra></extra>"))
    return fig


def _tile(label: str, value: str) -> str:
    return (
        f'<div class="tile"><div class="tile-label">{label}</div>'
        f'<div class="tile-value">{value}</div></div>'
    )


def build_dashboard(df: pd.DataFrame, pg: pd.DataFrame, summary: dict,
                    title: str, outfile: str) -> None:
    """収束モニタの静的ダッシュボード(単一HTML)を書き出す。

    Args:
        df: `SolveMonitor.to_frame` の出力(bound 推移)。
        pg: `primal_gap_series` の出力(空なら primal gap 図は省略)。
        summary: `solve_with_monitor` が返すサマリ dict。
        title: ページ見出し。
        outfile: 出力先 HTML パス。
    """
    figs = [fig_bounds(df), fig_gap(df)]
    if not pg.empty:
        figs.append(fig_primal_gap(pg))

    pi = pg["pintegral"].iloc[-1] if not pg.empty else None
    tiles = [
        _tile("ステータス", str(summary["status"])),
        _tile("目的値", f"{summary['objective']:,.1f}" if summary["objective"] is not None else "—"),
        _tile("Gap", f"{summary['gap'] * 100:.2f}%" if summary["gap"] is not None else "—"),
        _tile("ノード数", f"{summary['nodes']:,}"),
        _tile("求解時間", f"{summary['time']:.1f}s"),
        _tile("Primal Integral", f"{pi:.2f}" if pi is not None else "—"),
    ]

    chart_html = "".join(
        '<div class="chart">'
        + f.to_html(full_html=False, include_plotlyjs=(i == 0), config=dict(displayModeBar=False))
        + "</div>"
        for i, f in enumerate(figs)
    )
    html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>{title}</title>
<style>
  body {{ margin:0; background:{C['page']}; color:{C['ink']};
         font-family:{FONT}; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:24px 16px; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:16px; }}
  .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:16px; }}
  .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
           border-radius:8px; padding:10px 14px; min-width:110px; }}
  .tile-label {{ font-size:11px; color:{C['muted']}; }}
  .tile-value {{ font-size:20px; }}
  .chart {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
            border-radius:8px; margin-bottom:12px; overflow:hidden; }}
</style></head>
<body><div class="wrap">
<h1>{title}</h1>
<div class="sub">SCIP収束モニタ — Eventhdlrで取得したbound推移(Phase 1)</div>
<div class="tiles">{''.join(tiles)}</div>
{chart_html}
</div></body></html>"""
    with open(outfile, "w", encoding="utf-8") as f:
        f.write(html)
