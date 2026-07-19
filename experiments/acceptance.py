"""受け入れ検証ハーネス (Acceptance harness for Phase 13 sample clusters).

Phase 13 のテーマカタログで新規/精緻化するサンプルモデルが「診断・改善の題材として
成立するか」を機械的に判定する共通部品。以降の全クラスタ(T1..T7)で再利用する。

各モデル(``build_model(scale=...)`` を持つ)に対して:
  (a) 小scale: 実行可能解が出て有限目的値に達し、time_limit(既定120s)以内に最適到達するか
      → テスト・ハンズオンで使える軽さの担保(実行可能性の担保も兼ねる)。
  (b) 既定scale: 30秒 ``mk.analyze`` を実行し、gap と発火findings を計測。

判定(Phase 13 受け入れ基準):
  PASS = 「30秒でgap>=10%」 または 「非自明findingsが発火」。
  非自明 = symmetry_info / decomposable(=good・対応不要の情報系)以外の finding。
           すなわち weak_relaxation / wide_term_range / dual_stall / numerical_scale / gpu_primal。

使い方:
    uv run python experiments/acceptance.py \
        --models samples.manufacturing_and_blending.petroleum_pooling \
                 samples.manufacturing_and_blending.foundry_charge_mix_multiperiod \
                 samples.physics_and_control_minlp.water_network_reuse \
        --out results/acceptance_t1.md

    # scale名を変えたい場合(既定は small / default)
    uv run python experiments/acceptance.py --models <mod> --small-scale small --default-scale default
"""
from __future__ import annotations

import argparse
import importlib
import io
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import minlpkit as mk  # noqa: E402

# good(対応不要の情報系)= 自明。これ以外の発火は「非自明」とみなす。
TRIVIAL_FINDINGS = {"symmetry_info", "decomposable"}
GAP_THRESHOLD = 0.10  # 30秒でこれ以上残れば診断の題材になる


def _import_build_fn(dotted: str):
    """'samples.pkg.module' から build_model を取り出す。"""
    mod = importlib.import_module(dotted)
    fn = getattr(mod, "build_model", None)
    if fn is None:
        raise AttributeError(f"{dotted} に build_model がありません")
    return fn


def check_small_optimal(build_fn, scale: str, time_limit: float) -> dict:
    """小scaleで実行可能解+最適到達を確認する。"""
    t0 = time.perf_counter()
    model = build_fn(scale=scale)
    model.hideOutput()
    model.setParam("limits/time", time_limit)
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        model.optimize()
    status = model.getStatus()
    nsols = model.getNSols()
    obj = model.getObjVal() if nsols > 0 else None
    wall = time.perf_counter() - t0
    feasible = nsols > 0 and obj is not None and abs(obj) < 1e18
    optimal = status == "optimal"
    del model
    return dict(status=status, nsols=nsols, obj=obj, wall=round(wall, 1),
                feasible=feasible, optimal=optimal)


def check_default_diagnostic(build_fn, scale: str, time_limit: float) -> dict:
    """既定scaleで analyze を回し、gap と発火findings を測る。"""
    t0 = time.perf_counter()
    buf = io.StringIO()
    with redirect_stdout(buf), redirect_stderr(buf):
        report = mk.analyze(lambda: build_fn(scale=scale),
                            name="acceptance", time_limit=time_limit)
    m = report.metrics
    fids = [f["id"] for f in report.findings]
    nontrivial = [f for f in fids if f not in TRIVIAL_FINDINGS]
    gap = m.get("gap")
    wall = time.perf_counter() - t0
    gap_ok = gap is not None and gap >= GAP_THRESHOLD
    passed = gap_ok or len(nontrivial) > 0
    return dict(gap=gap, nodes=m.get("nodes"), nsols=m.get("nsols"),
                has_nonlinear=m.get("has_nonlinear"),
                findings=fids, nontrivial=nontrivial,
                gap_ok=gap_ok, passed=passed, wall=round(wall, 1))


def run(models: list[str], small_scale: str, default_scale: str,
        small_time: float, default_time: float) -> list[dict]:
    rows = []
    for dotted in models:
        name = dotted.rsplit(".", 1)[-1]
        print(f"\n=== {name} ===", flush=True)
        row = {"model": name, "dotted": dotted}
        try:
            build_fn = _import_build_fn(dotted)
        except Exception as e:  # noqa: BLE001
            print(f"  IMPORT ERROR: {e}", flush=True)
            row.update(error=f"import: {type(e).__name__}: {e}", passed=False)
            rows.append(row)
            continue

        print(f"  [small={small_scale}] 最適到達確認(<= {small_time:g}s) ...", flush=True)
        try:
            small = check_small_optimal(build_fn, small_scale, small_time)
            print(f"    status={small['status']} obj={small['obj']} "
                  f"nsols={small['nsols']} ({small['wall']}s)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"    SMALL ERROR: {type(e).__name__}: {e}", flush=True)
            small = dict(status="error", nsols=0, obj=None, wall=0.0,
                         feasible=False, optimal=False, error=str(e))

        print(f"  [default={default_scale}] {default_time:g}s analyze ...", flush=True)
        try:
            dfl = check_default_diagnostic(build_fn, default_scale, default_time)
            gaptxt = f"{dfl['gap']:.1%}" if dfl["gap"] is not None else "—"
            print(f"    gap={gaptxt} nodes={dfl['nodes']} nsols={dfl['nsols']} "
                  f"findings={dfl['findings']} PASS={dfl['passed']} ({dfl['wall']}s)",
                  flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"    DEFAULT ERROR: {type(e).__name__}: {e}", flush=True)
            dfl = dict(gap=None, nodes=None, nsols=None, has_nonlinear=None,
                       findings=[], nontrivial=[], gap_ok=False, passed=False,
                       wall=0.0, error=str(e))

        row["small"] = small
        row["default"] = dfl
        # 全体PASS: 小scaleで実行可能(できれば最適) かつ 既定scaleが受け入れ基準
        row["small_ok"] = small.get("feasible", False)
        row["passed"] = bool(small.get("feasible", False) and dfl.get("passed", False))
        rows.append(row)
    return rows


def to_markdown(rows: list[dict], small_scale: str, default_scale: str,
                small_time: float, default_time: float) -> str:
    L = []
    L.append("# 受け入れ検証結果 (Phase 13)\n")
    L.append("`experiments/acceptance.py` による自動判定。\n")
    L.append(f"- 小scale=`{small_scale}`(最適到達確認, <= {small_time:g}s) / "
             f"既定scale=`{default_scale}`({default_time:g}s analyze)")
    L.append(f"- 受け入れ基準: **{default_time:g}秒で gap>={GAP_THRESHOLD:.0%}** "
             "または **非自明findings発火**(symmetry_info/decomposable 以外)")
    npass = sum(1 for r in rows if r.get("passed"))
    L.append(f"- 判定: **{npass}/{len(rows)} PASS**\n")

    L.append("| model | small status | small obj | small(s) | "
             "default gap | nodes | nsols | findings | 判定 |")
    L.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        if r.get("error"):
            L.append(f"| {r['model']} | IMPORT ERROR | — | — | — | — | — | "
                     f"{r['error']} | ❌ FAIL |")
            continue
        s = r["small"]
        d = r["default"]
        gaptxt = f"{d['gap']:.1%}" if d.get("gap") is not None else "—"
        objtxt = f"{s['obj']:.4g}" if s.get("obj") is not None else "—"
        fids = ", ".join(f"`{f}`" for f in d.get("findings", [])) or "—"
        verdict = "✅ PASS" if r.get("passed") else "❌ FAIL"
        reason = []
        if d.get("gap_ok"):
            reason.append(f"gap {gaptxt}≥{GAP_THRESHOLD:.0%}")
        if d.get("nontrivial"):
            reason.append("非自明:" + ",".join(d["nontrivial"]))
        L.append(f"| {r['model']} | {s['status']} | {objtxt} | {s['wall']} | "
                 f"{gaptxt} | {d.get('nodes')} | {d.get('nsols')} | {fids} | "
                 f"{verdict} |")
    L.append("")
    L.append("判定理由(PASS根拠):")
    for r in rows:
        if r.get("error") or not r.get("default"):
            continue
        d = r["default"]
        why = []
        if d.get("gap_ok"):
            why.append(f"gap {d['gap']:.1%} ≥ {GAP_THRESHOLD:.0%}")
        if d.get("nontrivial"):
            why.append("非自明findings " + ",".join(d["nontrivial"]))
        if not r.get("small_ok"):
            why.append("(小scale実行可能解なし=要調整)")
        L.append(f"- **{r['model']}**: {'; '.join(why) if why else '基準未達(要調整)'}")
    L.append("")
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", nargs="+", required=True,
                    help="ドット区切りのimportパス(例 samples.manufacturing_and_blending.petroleum_pooling)")
    ap.add_argument("--small-scale", default="small")
    ap.add_argument("--default-scale", default="default")
    ap.add_argument("--small-time", type=float, default=120.0)
    ap.add_argument("--default-time", type=float, default=30.0)
    ap.add_argument("--out", default=None, help="Markdown出力先(results/acceptance_<tag>.md)")
    args = ap.parse_args()

    rows = run(args.models, args.small_scale, args.default_scale,
               args.small_time, args.default_time)
    md = to_markdown(rows, args.small_scale, args.default_scale,
                     args.small_time, args.default_time)
    print("\n" + "=" * 60)
    npass = sum(1 for r in rows if r.get("passed"))
    print(f"受け入れ: {npass}/{len(rows)} PASS", flush=True)
    if args.out:
        out = Path(args.out)
        if not out.is_absolute():
            out = ROOT / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
        print(f"[out] {out}", flush=True)


if __name__ == "__main__":
    main()
