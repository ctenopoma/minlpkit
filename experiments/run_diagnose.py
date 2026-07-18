"""診断ダッシュボード: 観測量を収集→診断ルール適用→改善提案を表示 (Phase 3)

Phase 1-2 の収集器を実際に走らせてモデルの観測量(metrics)を集め、
diagnose.py のルールに通して「検出した症状→推薦する改善→根拠」を1画面に出す。

実行: uv run python experiments/run_diagnose.py --model plant --time 20
出力: results/diagnose_<model>.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from run_tree import C, FONT
from viz.attribution import (detect_stalls, gain_by_kind, solve_and_attribute)
from viz.diagnose import evaluate
from viz.static_diag import (constraint_ratio, extract_coefficients,
                             linking_constraints, residual_scale, scale_summary)
from viz.symmetry import detect_symmetry
from viz.violation import collect_root_violations, violation_by_type

MODELS = {"uc": "unit_commitment", "sched": "scheduling",
          "plant": "scheduling_plant", "facility": "facility",
          "parallel": "parallel_machines"}
SEV_COLOR = {"good": "#0ca30c", "warning": "#fab219",
             "serious": "#ec835a", "critical": "#d03b3b"}
SEV_LABEL = {"good": "好機", "warning": "注意", "serious": "重大", "critical": "危機"}


def collect_metrics(model_key: str, time_limit: float) -> dict:
    module_name = MODELS[model_key]
    module = __import__(module_name)
    m: dict = {}

    # --- 動的観測: 双対境界の帰属・停滞・空間分枝比率 ---
    d, summ = solve_and_attribute(module.build_model(), time_limit=time_limit, gap_limit=0.01)
    total_gain = d["dual_gain"].sum() if not d.empty else 0.0
    gk = gain_by_kind(d).set_index("kind")["dual_gain"] if not d.empty else {}
    m["gap"] = summ["gap"]
    m["spatial_share"] = (gk.get("spatial", 0.0) / total_gain) if total_gain > 0 else 0.0
    m["n_stalls"] = len(detect_stalls(d)) if not d.empty else 0
    m["nodes"] = summ["nodes"]

    # --- 非線形制約の違反(ルート緩和)。非線形制約があるモデルのみ ---
    probe = module.build_model()
    has_nonlinear = any(c.isNonlinear() for c in probe.getConss())
    if has_nonlinear:
        try:
            vdf = collect_root_violations(module.build_model())
            if not vdf.empty:
                vt = violation_by_type(vdf).iloc[0]
                m["bottleneck_type"] = vt["ctype"]
                m["bottleneck_rel_viol"] = float(vt["mean_rel"])
        except Exception:
            pass

    # --- 静的: 係数スケール(presolve前)と残存(presolve後)・結合制約 ---
    cdf = extract_coefficients(module.build_model())
    s = scale_summary(cdf)
    m["coef_ratio"] = s["ratio"]
    m["bigm_count"] = len(s["bigm"])
    # SCIPが自動で締めた分を除いた残存スケール(診断はこちらで判断)
    rs = residual_scale(module.build_model())
    m["residual_coef_ratio"] = rs["ratio"]
    m["residual_bigm_count"] = len(rs["bigm"])
    lk = linking_constraints(module.build_model())
    if not lk.empty:
        m["max_linking_groups"] = int(lk.iloc[0]["n_groups"])
        m["n_heavy_linking"] = int((lk["n_groups"] >= lk.iloc[0]["n_groups"]).sum())

    # --- 対称性(非線形制約ありは不確定=sym_sound=False) ---
    _, sy = detect_symmetry(module.build_model())
    m["n_sym_groups"] = sy["n_groups"]
    m["largest_sym_group"] = sy["largest_group"]
    m["sym_sound"] = sy["sound"]

    # --- 区間演算(plantのみ) ---
    if model_key == "plant":
        from viz.plant_terms import evaluate_terms
        tdf = evaluate_terms()
        m["widest_term"] = tdf.iloc[0]["term"]
        m["widest_term_rel"] = float(tdf.iloc[0]["rel_width"])
    return m


def _finding_card(f: dict) -> str:
    color = SEV_COLOR.get(f["severity"], "#898781")
    links = " ".join(
        f'<a href="{l}" style="color:{C["s1"] if False else "#2a78d6"};">{l}</a>'
        for l in f["links"])
    return f"""
    <div class="finding" style="border-left:4px solid {color};">
      <div class="fhead">
        <span class="badge" style="background:{color};">{SEV_LABEL.get(f['severity'], '')}</span>
        <span class="symptom">{f['symptom']}</span>
      </div>
      <div class="frow"><span class="k">原因</span> {f['cause']}</div>
      <div class="frow"><span class="k">推薦</span> <b>{f['recommendation']}</b></div>
      <div class="frow"><span class="k">根拠</span> {f['evidence']}</div>
      <div class="frow"><span class="k">参照</span> {links}</div>
    </div>"""


def _metric_row(m: dict) -> str:
    items = [
        ("最終gap", f"{m['gap'] * 100:.1f}%" if m.get("gap") is not None else "—"),
        ("空間分枝の双対寄与", f"{m.get('spatial_share', 0) * 100:.0f}%"),
        ("停滞区間", f"{m.get('n_stalls', 0)}"),
        ("支配ボトルネック", f"{m.get('bottleneck_type', '—')}"),
        ("係数max/min比", f"{m.get('coef_ratio', 0):.2g}" if m.get("coef_ratio") else "—"),
        ("Big-M候補", f"{m.get('bigm_count', 0)}"),
        ("最大対称群", f"{m.get('largest_sym_group', 0)}"),
        ("最大結合グループ", f"{m.get('max_linking_groups', 0)}"),
    ]
    return "".join(
        f'<div class="tile"><div class="tile-label">{k}</div>'
        f'<div class="tile-value">{v}</div></div>' for k, v in items)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    ap.add_argument("--time", type=float, default=20.0)
    args = ap.parse_args()

    print(f"collecting metrics for {MODELS[args.model]} (solve {args.time}s) ...")
    metrics = collect_metrics(args.model, args.time)
    findings = evaluate(metrics)
    print(f"detected {len(findings)} symptoms:")
    for f in findings:
        print(f"  [{f['severity']}] {f['symptom']} -> {f['recommendation']}")

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    out = outdir / f"diagnose_{args.model}.html"
    cards = "".join(_finding_card(f) for f in findings) or \
        '<div class="finding">検出された症状はありません。</div>'
    html = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<title>診断サマリ {args.model}</title>
<style>
 body {{ margin:0; background:{C['page']}; color:{C['ink']}; font-family:{FONT}; }}
 .wrap {{ max-width:940px; margin:0 auto; padding:22px 16px; }}
 h1 {{ font-size:18px; margin:0 0 4px; }}
 .sub {{ color:{C['ink2']}; font-size:12px; margin-bottom:14px; }}
 h2 {{ font-size:14px; margin:18px 0 8px; color:{C['ink2']}; }}
 .tiles {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px; }}
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
 .frow .k {{ display:inline-block; width:44px; color:{C['muted']}; }}
 a {{ text-decoration:none; }}
</style></head><body><div class="wrap">
<h1>診断サマリと改善提案(Phase 3)</h1>
<div class="sub">{MODELS[args.model]} — Phase 1-2の観測量を診断ルールに通した結果。推薦はPhase 4で実施・検証する</div>
<h2>観測量</h2>
<div class="tiles">{_metric_row(metrics)}</div>
<h2>検出した症状 → 推薦する改善({len(findings)}件)</h2>
{cards}
</div></body></html>"""
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
