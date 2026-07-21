"""Report の統合ダッシュボードHTML描画 (Phase 5)。

診断サマリ(観測量タイル + 症状カード)を単一HTMLにまとめる。詳細な個別可視化
(tree/violation/attribution 等)へのリンクも張る。
"""

from __future__ import annotations

from pathlib import Path

# 参照パレット(dataviz, light)
C = dict(surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
SEV_COLOR = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b"}
SEV_LABEL = {"good": "好機", "warning": "注意", "serious": "重大", "critical": "危機"}


def _tile(label, value):
    return (f'<div class="tile"><div class="tile-label">{label}</div>'
            f'<div class="tile-value">{value}</div></div>')


def _metric_tiles(m: dict) -> str:
    def g(k, fmt="{}", scale=1.0, suffix=""):
        v = m.get(k)
        return "—" if v is None else (fmt.format(v * scale) + suffix)
    items = [
        ("最終gap", g("gap", "{:.1f}", 100, "%")),
        ("空間分枝の双対寄与", g("spatial_share", "{:.0f}", 100, "%")),
        ("停滞区間", g("n_stalls")),
        ("支配ボトルネック", m.get("bottleneck_type", "—")),
        ("残存係数比", g("residual_coef_ratio", "{:.2g}")),
        ("残存Big-M", g("residual_bigm_count")),
        ("最大対称群", g("largest_sym_group")),
        ("最大結合グループ", g("max_linking_groups")),
    ]
    return "".join(_tile(k, v) for k, v in items)


def _finding_card(f: dict) -> str:
    color = SEV_COLOR.get(f["severity"], "#898781")
    links = " ".join(f'<a href="{l}">{l}</a>' for l in f.get("links", []))
    return f"""
    <div class="finding" style="border-left:4px solid {color};">
      <div class="fhead"><span class="badge" style="background:{color};">{SEV_LABEL.get(f['severity'],'')}</span>
      <span class="symptom">{f['symptom']}</span></div>
      <div class="frow"><span class="k">原因</span> {f['cause']}</div>
      <div class="frow"><span class="k">推薦</span> <b>{f['recommendation']}</b></div>
      <div class="frow"><span class="k">手順</span> <span class="recipe">{f.get('recipe','')}</span></div>
      <div class="frow"><span class="k">根拠</span> {f['evidence']}</div>
      <div class="frow"><span class="k">参照</span> {links}</div>
    </div>"""


def render_report(report, path: str) -> None:
    cards = "".join(_finding_card(f) for f in report.findings) or \
        '<div class="finding">検出された症状はありません。</div>'
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>minlpkit report — {report.name}</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:940px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 h2 {{ font-size:14px; margin:18px 0 8px; color:{C['ink2']}; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; }}
 .tile {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
          border-radius:8px; padding:9px 13px; min-width:120px; }}
 .tile-label {{ font-size:11px; color:{C['muted']}; }}
 .tile-value {{ font-size:18px; font-variant-numeric:tabular-nums; }}
 .finding {{ background:{C['surface']}; border:1px solid rgba(11,11,11,0.10);
             border-radius:8px; padding:12px 14px; margin-bottom:10px; }}
 .fhead {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }}
 .badge {{ color:#fff; font-size:11px; font-weight:700; padding:2px 9px; border-radius:999px; }}
 .symptom {{ font-size:14px; font-weight:600; }}
 .frow {{ font-size:12.5px; color:{C['ink2']}; line-height:1.7; }}
 .frow .k {{ display:inline-block; width:44px; color:{C['muted']}; vertical-align:top; }}
 .recipe {{ display:inline-block; background:#eef5fd; border-radius:4px; padding:1px 7px;
            font-family:ui-monospace,monospace; font-size:11.5px; }}
 a {{ color:#2a78d6; text-decoration:none; }}
</style></head><body><div class="wrap">
<h1>minlpkit レポート — {report.name}</h1>
<div class="sub">analyze() による観測量収集・診断・改善提案を一気通貫で表示</div>
<h2>観測量</h2>
<div class="tiles">{_metric_tiles(report.metrics)}</div>
<h2>検出した症状 → 推薦する改善({len(report.findings)}件)</h2>
{cards}
</div></body></html>"""
    Path(path).write_text(html, encoding="utf-8")
