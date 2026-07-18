"""観測量収集 → 診断のパイプライン (Phase 5, model非依存)。

build_fn(zero-arg callable が新しい Model を返す)を渡すと、Phase 1-4の収集器を
実際に走らせて metrics を集め、診断ルールを適用して Report を返す。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .collectors.attribution import (detect_stalls, gain_by_kind,
                                     solve_and_attribute)
from .collectors.diagnose import evaluate
from .collectors.static_diag import (extract_coefficients, linking_constraints,
                                     residual_scale, scale_summary)
from .collectors.symmetry import detect_symmetry
from .collectors.violation import collect_root_violations, violation_by_type

BuildFn = Callable[[], "object"]  # () -> pyscipopt.Model


def collect_metrics(build_fn: BuildFn, time_limit: float = 20.0,
                    interval_terms_fn: Optional[Callable[[], pd.DataFrame]] = None) -> dict:
    """build_fn のモデルから観測量(metrics)を集める(model非依存)。

    双対境界の帰属・停滞・空間分枝比率(動的)、非線形制約の違反、係数スケール・結合制約
    (静的)、対称性を収集して1つの dict にまとめる。診断ルールはこの dict を入力にする。

    Args:
        build_fn: 引数なしで新しい ``pyscipopt.Model`` を返す callable。収集器が複数回
            呼ぶため、毎回新しいモデルを返すこと(使い回すと状態が汚れる)。
        time_limit: 動的収集(求解して分枝を観測する)の時間制限[秒]。
        interval_terms_fn: 省略可。非線形項の区間(値域)を返す関数。渡すと最大相対幅を
            metrics に追加する(plant 等の worked example 用)。

    Returns:
        dict: 観測量。``gap`` / ``spatial_share`` / ``n_stalls`` / ``nodes`` /
        ``bottleneck_type`` / ``bottleneck_rel_viol`` / ``coef_ratio`` /
        ``residual_coef_ratio`` / ``residual_bigm_count`` / ``max_linking_groups`` /
        ``n_sym_groups`` / ``largest_sym_group`` / ``sym_sound`` など(モデルにより一部欠落)。

    Note:
        ``build_fn()`` の結果は必ずローカル変数に保持すること。反復中に GC されると
        PySCIPOpt がアクセス違反(segfault)を起こす(FINDINGS.md §5)。
    """
    m: dict = {}

    # 動的: 双対境界の帰属・停滞・空間分枝比率
    d, summ = solve_and_attribute(build_fn(), time_limit=time_limit, gap_limit=0.01)
    total_gain = d["dual_gain"].sum() if not d.empty else 0.0
    gk = gain_by_kind(d).set_index("kind")["dual_gain"] if not d.empty else {}
    m["gap"] = summ["gap"]
    m["spatial_share"] = (gk.get("spatial", 0.0) / total_gain) if total_gain > 0 else 0.0
    m["n_stalls"] = len(detect_stalls(d)) if not d.empty else 0
    m["nodes"] = summ["nodes"]

    # 非線形制約の違反(非線形制約があるモデルのみ)
    # 注: build_fn()の結果は必ずローカル変数に保持する(反復中にGCされるとPySCIPOptが
    #     アクセス違反=segfaultするため)。
    probe = build_fn()
    has_nonlinear = any(c.isNonlinear() for c in probe.getConss())
    del probe
    if has_nonlinear:
        try:
            vdf = collect_root_violations(build_fn())
            if not vdf.empty:
                vt = violation_by_type(vdf).iloc[0]
                m["bottleneck_type"] = vt["ctype"]
                m["bottleneck_rel_viol"] = float(vt["mean_rel"])
        except Exception:
            pass

    # 静的: 係数スケール(前/残存)・結合制約
    mc = build_fn()
    s = scale_summary(extract_coefficients(mc))
    m["coef_ratio"], m["bigm_count"] = s["ratio"], len(s["bigm"])
    rs = residual_scale(build_fn())
    m["residual_coef_ratio"], m["residual_bigm_count"] = rs["ratio"], len(rs["bigm"])
    ml = build_fn()
    lk = linking_constraints(ml)
    if not lk.empty:
        m["max_linking_groups"] = int(lk.iloc[0]["n_groups"])
        m["n_heavy_linking"] = int((lk["n_groups"] >= lk.iloc[0]["n_groups"]).sum())

    # 対称性(非線形ありは不確定=sym_sound=False)
    _, sy = detect_symmetry(build_fn())
    m["n_sym_groups"], m["largest_sym_group"], m["sym_sound"] = \
        sy["n_groups"], sy["largest_group"], sy["sound"]

    # 区間演算(任意)
    if interval_terms_fn is not None:
        tdf = interval_terms_fn()
        if not tdf.empty:
            m["widest_term"] = tdf.iloc[0]["term"]
            m["widest_term_rel"] = float(tdf.iloc[0]["rel_width"])
    return m


@dataclass
class Report:
    """``analyze`` の結果を保持する。観測量と診断結果、出力メソッドを持つ。

    Attributes:
        name: レポート名(モデル名など)。
        metrics: ``collect_metrics`` が集めた観測量 dict。
        findings: 発火した診断ルールのlist(重要度順)。各要素は
            ``symptom`` / ``cause`` / ``recommendation`` / ``evidence`` / ``recipe`` /
            ``severity`` / ``links`` を持つ dict。

    Example:
        >>> import minlpkit as mk
        >>> from pyscipopt import Model
        >>> def build():
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(vtype="B"); y = m.addVar(vtype="B")
        ...     m.addCons(x + y <= 1); m.setObjective(x + y, "maximize")
        ...     return m
        >>> report = mk.analyze(build, name="toy", time_limit=5)
        >>> isinstance(report.summary(), str)
        True
    """
    name: str
    metrics: dict
    findings: list[dict] = field(default_factory=list)

    def summary(self) -> str:
        """検出症状を人間可読の複数行テキストにして返す。"""
        lines = [f"[{self.name}] 検出症状 {len(self.findings)}件:"]
        for f in self.findings:
            lines.append(f"  [{f['severity']}] {f['symptom']} -> {f['recommendation']}")
        return "\n".join(lines)

    def dashboard(self, path: str) -> None:
        """観測量と診断を1枚にまとめた統合ダッシュボードHTMLを ``path`` に書き出す。

        Args:
            path: 出力先HTMLパス(例: ``results/report_plant.html``)。
        """
        from .render import render_report
        render_report(self, path)


def analyze(build_fn: BuildFn, name: str = "model", time_limit: float = 20.0,
            interval_terms_fn: Optional[Callable[[], pd.DataFrame]] = None) -> Report:
    """観測量収集 + 診断を一気通貫で行い ``Report`` を返す。

    ``collect_metrics`` で観測量を集め、``evaluate`` で診断ルールを適用する。可視化→診断の
    入口となる関数。返り値の ``report.dashboard(path)`` で統合HTMLを出力できる。

    Args:
        build_fn: 引数なしで新しい ``Model`` を返す callable。
        name: レポート名(モデル名など)。
        time_limit: 動的収集の時間制限[秒]。
        interval_terms_fn: 省略可。非線形項の区間を返す関数(``collect_metrics`` 参照)。

    Returns:
        Report: 観測量 ``metrics`` と診断 ``findings`` を持つレポート。

    Example:
        >>> import minlpkit as mk
        >>> from pyscipopt import Model
        >>> def build():
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(vtype="B"); y = m.addVar(vtype="B")
        ...     m.addCons(x + y <= 1); m.setObjective(x + y, "maximize")
        ...     return m
        >>> report = mk.analyze(build, name="toy", time_limit=5)
        >>> report.name
        'toy'
    """
    metrics = collect_metrics(build_fn, time_limit=time_limit,
                              interval_terms_fn=interval_terms_fn)
    findings = evaluate(metrics)
    return Report(name=name, metrics=metrics, findings=findings)
