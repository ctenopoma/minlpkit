"""GPU実験(cuOpt×SCIP 3アーム比較)結果のPlotlyダッシュボード生成

`run_gpu_heuristic.py` が出力する `results/gpu/<tag>_compare.csv`
(列: arm, time, objective。arm は scip/cuopt/hybrid、いずれも最小化問題)を読み、
アーム別スタットタイル(TTFF・最終best・primal integral)とincumbent軌跡の
階段チャートを単一HTMLにまとめる。dataviz スキルの参照パレット(検証済み)を使用。

実行例:
  uv run python experiments/gpu_dashboard.py --tag gap_large
  uv run python experiments/gpu_dashboard.py   # results/gpu/ 配下の *_compare.csv を一括処理

出力: results/gpu/<tag>_compare.html
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs

ROOT = Path(__file__).resolve().parents[1]
GPUDIR = ROOT / "results" / "gpu"

# 参照パレット (dataviz references/palette.md, light固定。ローカル分析用HTMLのため)
C = dict(
    surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
    muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
)
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

# アームの固定表示順・固定色(カテゴリカルslot1/2/3、cycleしない)。
# validate_palette.js で3色とも adjacent/normal-vision floor をPASS済み
# (#e87ba4 のみ surface contrast WARN → 凡例の直接ラベル + 表ビューで relief)
ARMS = ["scip", "cuopt", "hybrid"]
ARM_LABEL = {"scip": "SCIP (CPU)", "cuopt": "cuOpt (GPU)", "hybrid": "cuOpt→SCIP warm start"}
ARM_COLOR = {"scip": "#2a78d6", "cuopt": "#008300", "hybrid": "#e87ba4"}

NOSOL = 1e19  # これ以上は「解なし」センチネル(SCIPのinfinity=1e20)とみなす閾値


# --------------------------------------------------------------------------
# 集計
# --------------------------------------------------------------------------

def _arm_stats(df: pd.DataFrame, arm: str, t_end: float, ref: float | None) -> dict:
    """1アーム分の TTFF・best-so-far軌跡・primal integral を求める。"""
    sub = df[df["arm"] == arm].sort_values("time")
    real = sub[sub["objective"] < NOSOL]
    if real.empty:
        return dict(arm=arm, has_sol=False, ttff=None, best=None, pintegral=None, traj=None)

    traj = real[["time", "objective"]].copy()
    traj["best_so_far"] = traj["objective"].cummin()  # 最小化: incumbentの改善履歴
    ttff = float(traj["time"].iloc[0])
    best = float(traj["best_so_far"].iloc[-1])
    pintegral = _primal_integral(traj, ttff, t_end, ref) if ref is not None else None
    return dict(arm=arm, has_sol=True, ttff=ttff, best=best, pintegral=pintegral, traj=traj)


def _primal_integral(traj: pd.DataFrame, ttff: float, t_end: float, ref: float) -> float:
    """primal gap p(t) = |best_so_far(t)-ref| / max(|best_so_far|,|ref|,1) の区分定数積分。

    [0, ttff) は可行解が無い区間なので最大ペナルティ p=1 とする(Achterberg流)。
    t_end は当該タグ内で観測された最終共通時刻(全アーム合わせた最大time)。
    """
    area = max(ttff, 0.0) * 1.0
    times = traj["time"].to_numpy()
    vals = traj["best_so_far"].to_numpy()
    for i in range(len(times)):
        t0 = times[i]
        t1 = times[i + 1] if i + 1 < len(times) else t_end
        if t1 <= t0:
            continue
        denom = max(abs(vals[i]), abs(ref), 1.0)
        p = abs(vals[i] - ref) / denom
        area += p * (t1 - t0)
    return area


# --------------------------------------------------------------------------
# 描画
# --------------------------------------------------------------------------

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
        margin=dict(l=64, r=20, t=48, b=48), height=420,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=1.0, xanchor="right",
                    font=dict(size=11, color=C["ink2"]), bgcolor="rgba(0,0,0,0)"),
    )


def _fig_trajectory(stats: list[dict], title: str) -> go.Figure:
    """incumbent軌跡(best-so-far)の階段チャート。更新点にマーカー。"""
    fig = go.Figure(layout=_base_layout(f"{title} — incumbent軌跡", "目的関数値"))
    any_trace = False
    for s in stats:
        if not s["has_sol"]:
            continue
        traj = s["traj"]
        color = ARM_COLOR[s["arm"]]
        fig.add_trace(go.Scatter(
            x=traj["time"], y=traj["best_so_far"], name=ARM_LABEL[s["arm"]],
            mode="lines+markers",
            line=dict(color=color, width=2, shape="hv"),
            marker=dict(color=color, size=8, line=dict(color=C["surface"], width=1.5)),
            hovertemplate=f"{ARM_LABEL[s['arm']]} %{{y:,.1f}}<extra></extra>",
        ))
        any_trace = True
    if not any_trace:
        fig.add_annotation(
            text="全アームで可行解が得られませんでした", showarrow=False,
            font=dict(color=C["muted"], size=13), x=0.5, y=0.5, xref="paper", yref="paper")
    return fig


def _fmt_num(v: float | None, digits: int = 1) -> str:
    return "—" if v is None else f"{v:,.{digits}f}"


def _fmt_time(v: float | None) -> str:
    return "—" if v is None else f"{v:,.2f}s"


def _tile_row(s: dict) -> str:
    color = ARM_COLOR[s["arm"]]
    if not s["has_sol"]:
        return (
            f'<div class="arow"><div class="aname"><span class="dot" style="background:{color};"></span>'
            f'{ARM_LABEL[s["arm"]]}</div><div class="anosol">可行解なし</div></div>'
        )
    return f"""
    <div class="arow">
      <div class="aname"><span class="dot" style="background:{color};"></span>{ARM_LABEL[s['arm']]}</div>
      <div class="ametric"><div class="mlabel">TTFF</div><div class="mvalue">{_fmt_time(s['ttff'])}</div></div>
      <div class="ametric"><div class="mlabel">最終best</div><div class="mvalue">{_fmt_num(s['best'])}</div></div>
      <div class="ametric"><div class="mlabel">Primal Integral</div><div class="mvalue">{_fmt_num(s['pintegral'], 2)}</div></div>
    </div>"""


def _table_view(df: pd.DataFrame) -> str:
    """アクセシビリティ用の表ビュー(生データ、折りたたみ)。"""
    real = df[df["objective"] < NOSOL].sort_values(["arm", "time"])
    if real.empty:
        return ""
    rows = "".join(
        f'<tr><td><span class="dot" style="background:{ARM_COLOR.get(r.arm, C["muted"])};"></span>'
        f'{ARM_LABEL.get(r.arm, r.arm)}</td><td>{r.time:,.2f}</td><td>{r.objective:,.1f}</td></tr>'
        for r in real.itertuples()
    )
    return f"""
    <details class="tableview">
      <summary>表ビュー(incumbent更新イベント {len(real)}件)</summary>
      <table><thead><tr><th>アーム</th><th>時刻 [s]</th><th>目的値</th></tr></thead>
      <tbody>{rows}</tbody></table>
    </details>"""


def build_dashboard(tag: str) -> Path:
    """1タグ分のCSVを読んでHTMLダッシュボードを書き出す。"""
    csv_path = GPUDIR / f"{tag}_compare.csv"
    df = pd.read_csv(csv_path)
    title = tag

    t_end = float(df["time"].max()) if not df.empty else 0.0
    real_all = df[df["objective"] < NOSOL]
    ref = float(real_all["objective"].min()) if not real_all.empty else None

    stats = [_arm_stats(df, a, t_end, ref) for a in ARMS]
    fig = _fig_trajectory(stats, title)

    tiles_html = "".join(_tile_row(s) for s in stats)
    chart_html = (
        '<div class="chart">'
        + fig.to_html(full_html=False, include_plotlyjs=False, config=dict(displayModeBar=False))
        + "</div>"
    )
    table_html = _table_view(df)
    no_sol_arms = [ARM_LABEL[s["arm"]] for s in stats if not s["has_sol"]]
    note = (
        f'<div class="note">可行解なし: {"、".join(no_sol_arms)}</div>' if no_sol_arms else ""
    )

    html = f"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>GPU実験比較 — {title}</title>
<style>
  body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:24px 16px; }}
  h1 {{ font-size:18px; margin:0 0 4px; }}
  .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:16px; }}
  .dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:6px; vertical-align:middle; }}
  .stats {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10); border-radius:8px;
            padding:12px 16px; margin-bottom:16px; }}
  .arow {{ display:flex; align-items:center; gap:24px; padding:8px 0; border-bottom:1px solid {C['grid']}; flex-wrap:wrap; }}
  .arow:last-child {{ border-bottom:none; }}
  .aname {{ width:220px; flex-shrink:0; font-size:13px; font-weight:600; }}
  .ametric {{ min-width:120px; }}
  .mlabel {{ font-size:11px; color:{C['muted']}; }}
  .mvalue {{ font-size:16px; font-variant-numeric:tabular-nums; }}
  .anosol {{ font-size:13px; color:{C['muted']}; font-style:italic; }}
  .chart {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
            border-radius:8px; margin-bottom:12px; overflow:hidden; }}
  .note {{ font-size:12px; color:{C['muted']}; margin-bottom:12px; }}
  .tableview {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10); border-radius:8px; padding:10px 14px; }}
  .tableview summary {{ cursor:pointer; font-size:12.5px; color:{C['ink2']}; }}
  .tableview table {{ width:100%; border-collapse:collapse; margin-top:8px; font-size:12px; }}
  .tableview th, .tableview td {{ text-align:left; padding:4px 8px; border-bottom:1px solid {C['grid']}; }}
  .tableview th {{ color:{C['muted']}; font-weight:600; }}
</style></head>
<body><div class="wrap">
<h1>GPU実験比較 — {title}</h1>
<div class="sub">cuOpt(GPU primal heuristics) × SCIP(CPU) 3アーム比較。scip=純SCIP、cuopt=cuOpt単体(RTX 5070 Ti/WSL2)、hybrid=cuOpt解をSCIPへwarm start注入</div>
<div class="stats">{tiles_html}</div>
{note}
{chart_html}
{table_html}
</div>
<script>{get_plotlyjs()}</script>
</body></html>"""
    out_path = GPUDIR / f"{tag}_compare.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main() -> None:
    ap = argparse.ArgumentParser(description="GPU実験比較CSV → Plotlyダッシュボード")
    ap.add_argument("--tag", help="results/gpu/<tag>_compare.csv を処理。省略時は全*_compare.csvを一括処理")
    args = ap.parse_args()

    if args.tag:
        tags = [args.tag]
    else:
        tags = sorted(p.stem.removesuffix("_compare") for p in GPUDIR.glob("*_compare.csv"))
        if not tags:
            print(f"[gpu_dashboard] {GPUDIR} に *_compare.csv が見つかりません")
            return

    for tag in tags:
        out_path = build_dashboard(tag)
        print(f"[gpu_dashboard] {tag}: {out_path}")


if __name__ == "__main__":
    main()
