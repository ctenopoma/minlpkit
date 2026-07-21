"""診断センサス: samplesの各モデルに mk.analyze を掛け、発火findingsを集計する。

サンプル群を「診断エンジンのベンチマーク」として使う。指定カテゴリの各 build_model() を
import し、mk.analyze(build_fn, time_limit=T) を実行、1サンプル1行に集約して
results/census.csv と docs/census.md 用の Markdown テーブルに出力する。

使い方:
    uv run python experiments/run_census.py --time 10
    uv run python experiments/run_census.py --time 10 --categories scheduling energy_and_microgrid

build_model が無い / 引数必須 / 実行時エラーのファイルは skip(理由) として表に記録する
(隠さない=方針)。
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import io
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples"
sys.path.insert(0, str(ROOT))

import minlpkit as mk  # noqa: E402

# 既定の対象カテゴリ(約40本)。全カテゴリはやらない(1本あたり複数solveで重い)。
DEFAULT_CATEGORIES = [
    "physics_and_control_minlp",
    "packing_and_cutting",
    "scheduling",
    "energy_and_microgrid",
]


def _load_build_fn(pyfile: Path):
    """pyfile から build_model を取り出す。取れなければ (None, 理由)。"""
    modname = f"census_{pyfile.parent.name}_{pyfile.stem}"
    spec = importlib.util.spec_from_file_location(modname, pyfile)
    if spec is None or spec.loader is None:
        return None, "spec生成失敗"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    try:
        # samples内の相互importに備え、サブディレクトリをpathに載せる
        if str(pyfile.parent) not in sys.path:
            sys.path.insert(0, str(pyfile.parent))
        spec.loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        return None, f"import失敗: {type(e).__name__}: {e}"
    fn = getattr(mod, "build_model", None)
    if fn is None:
        return None, "build_model無し"
    # 引数なしで呼べるか(default付きはOK)
    sig = inspect.signature(fn)
    required = [p for p in sig.parameters.values()
                if p.default is inspect.Parameter.empty
                and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    if required:
        return None, f"引数必須({', '.join(p.name for p in required)})"
    return fn, None


def _derive_status(metrics: dict) -> str:
    """metrics の gap から求解状況ラベルを導く(gap由来。真のSCIP statusではない)。"""
    gap = metrics.get("gap")
    if gap is None:
        return "no-gap"
    if gap < 1e-4:
        return "optimal"
    return f"gap {gap:.1%}"


def run_census(categories: list[str], time_limit: float) -> pd.DataFrame:
    rows: list[dict] = []
    for cat in categories:
        cdir = SAMPLES / cat
        if not cdir.is_dir():
            print(f"[warn] カテゴリ無し: {cat}", flush=True)
            continue
        pyfiles = sorted(p for p in cdir.glob("*.py") if p.stem != "__init__")
        for pf in pyfiles:
            name = pf.stem
            print(f"[{cat}/{name}] ...", end="", flush=True)
            t0 = time.perf_counter()
            build_fn, reason = _load_build_fn(pf)
            if build_fn is None:
                print(f" skip({reason})", flush=True)
                rows.append(dict(sample=name, category=cat, status="skip",
                                 gap=None, nodes=None, nsols=None, has_nonlinear=None,
                                 solve_time=None, n_findings=0, findings="",
                                 note=reason, wall=round(time.perf_counter() - t0, 1)))
                continue
            try:
                buf = io.StringIO()
                with redirect_stdout(buf), redirect_stderr(buf):
                    report = mk.analyze(lambda bf=build_fn: bf(), name=name,
                                        time_limit=time_limit)
                m = report.metrics
                fids = [f["id"] for f in report.findings]
                rows.append(dict(
                    sample=name, category=cat, status=_derive_status(m),
                    gap=(round(m["gap"], 4) if m.get("gap") is not None else None),
                    nodes=m.get("nodes"), nsols=m.get("nsols"),
                    has_nonlinear=m.get("has_nonlinear"),
                    solve_time=round(m.get("solve_time", 0.0), 2),
                    n_findings=len(fids), findings=";".join(fids),
                    note="", wall=round(time.perf_counter() - t0, 1)))
                print(f" {_derive_status(m)} findings=[{','.join(fids)}] "
                      f"({rows[-1]['wall']}s)", flush=True)
            except Exception as e:  # noqa: BLE001
                tb = traceback.format_exc(limit=2).strip().splitlines()[-1]
                print(f" ERROR({type(e).__name__})", flush=True)
                rows.append(dict(sample=name, category=cat, status="error",
                                 gap=None, nodes=None, nsols=None, has_nonlinear=None,
                                 solve_time=None, n_findings=0, findings="",
                                 note=f"{type(e).__name__}: {e}"[:120] or tb,
                                 wall=round(time.perf_counter() - t0, 1)))
    return pd.DataFrame(rows)


def _finding_id_list() -> list[str]:
    return [r.id for r in mk.RULES]


def write_markdown(df: pd.DataFrame, path: Path, time_limit: float) -> None:
    ok = df[~df["status"].isin(["skip", "error"])]
    all_ids = _finding_id_list()
    # findings別発火件数
    counts = {fid: 0 for fid in all_ids}
    for s in ok["findings"]:
        for fid in [x for x in s.split(";") if x]:
            counts[fid] = counts.get(fid, 0) + 1
    # 難しい上位(gap大)
    hard = ok[ok["gap"].notna()].copy()
    hard = hard.sort_values("gap", ascending=False).head(10)
    # 非線形サンプルでの weak_relaxation 発火率
    nl = ok[ok["has_nonlinear"] == True]  # noqa: E712
    nl_weak = nl[nl["findings"].str.contains("weak_relaxation")]
    weak_rate = (len(nl_weak) / len(nl)) if len(nl) else 0.0

    lines: list[str] = []
    lines.append("# 診断ベンチマーク結果\n")
    lines.append(
        "minlpkit の診断エンジン(`mk.analyze`)を samples の多数のモデルに一括適用し、"
        "どの症状(finding)がどのモデルで発火するかを集計した結果。\n")
    lines.append(
        f"- 対象カテゴリ: {', '.join(sorted(df['category'].unique()))}\n"
        f"- 各モデル `mk.analyze(build_model, time_limit={time_limit:g})` を1回実行\n"
        f"- 全 {len(df)} 本中 解析成功 {len(ok)} 本 / skip {int((df['status']=='skip').sum())} 本 "
        f"/ error {int((df['status']=='error').sum())} 本\n")
    lines.append("再現: `uv run python experiments/run_census.py --time "
                 f"{time_limit:g}`\n")

    lines.append("\n## 集計1: finding別 発火件数\n")
    lines.append("| finding id | 重要度 | 発火本数 |")
    lines.append("| --- | --- | --- |")
    sev = {r.id: r.severity for r in mk.RULES}
    for fid in sorted(all_ids, key=lambda x: -counts.get(x, 0)):
        lines.append(f"| `{fid}` | {sev.get(fid,'')} | {counts.get(fid,0)} |")

    lines.append("\n## 集計2: 難しいモデル上位(残存gap大)\n")
    lines.append("| sample | category | gap | nodes | nsols | findings |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for _, r in hard.iterrows():
        lines.append(f"| {r['sample']} | {r['category']} | {r['gap']:.1%} | "
                     f"{r['nodes']} | {r['nsols']} | {r['findings'] or '—'} |")

    lines.append("\n## 集計3: 非線形モデルでの weak_relaxation 発火率\n")
    lines.append(
        f"- 非線形モデル(`has_nonlinear=True`)は {len(nl)} 本。"
        f"うち `weak_relaxation` 発火は {len(nl_weak)} 本(**{weak_rate:.0%}**)。\n")
    if len(nl_weak):
        lines.append("発火モデル: " + ", ".join(f"`{s}`" for s in nl_weak["sample"]) + "\n")

    lines.append("\n## 全結果表\n")
    lines.append("| sample | category | status | gap | nodes | nsols | nl | findings | note |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for _, r in df.sort_values(["category", "sample"]).iterrows():
        gap = f"{r['gap']:.1%}" if pd.notna(r["gap"]) else "—"
        nl = "✓" if r["has_nonlinear"] else ("" if r["has_nonlinear"] is not None else "—")
        note = (r["note"] or "").replace("|", "/")
        lines.append(
            f"| {r['sample']} | {r['category']} | {r['status']} | {gap} | "
            f"{r['nodes'] if pd.notna(r['nodes']) else '—'} | "
            f"{r['nsols'] if pd.notna(r['nsols']) else '—'} | {nl} | "
            f"{r['findings'] or '—'} | {note} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--time", type=float, default=10.0, help="1モデルの解析時間制限[秒]")
    ap.add_argument("--categories", nargs="*", default=None,
                    help="対象カテゴリ(既定=4カテゴリ)")
    ap.add_argument("--out-csv", default=str(ROOT / "results" / "census.csv"))
    ap.add_argument("--out-md", default=str(ROOT / "docs" / "census.md"))
    args = ap.parse_args()

    cats = args.categories or DEFAULT_CATEGORIES
    print(f"=== 診断センサス: {cats} time_limit={args.time}s ===", flush=True)
    df = run_census(cats, args.time)

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False, encoding="utf-8")
    print(f"\n[out] {out_csv}", flush=True)

    out_md = Path(args.out_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(df, out_md, args.time)
    print(f"[out] {out_md}", flush=True)

    ok = df[~df["status"].isin(["skip", "error"])]
    print(f"\n解析成功 {len(ok)}/{len(df)} 本、"
          f"skip {int((df['status']=='skip').sum())}、"
          f"error {int((df['status']=='error').sum())}", flush=True)


if __name__ == "__main__":
    main()
