"""pipeline analyze の smoke テスト(facility を実ソルバーで解く)。"""
from __future__ import annotations

import minlpkit as mk
from minlpkit.pipeline import Report


def test_analyze_facility_smoke():
    """facility(線形MILP)で analyze が Report を返し、findings が list になる。"""
    import facility as fac  # conftest が samples/ を sys.path に追加済み

    report = mk.analyze(lambda: fac.build_model(), name="facility", time_limit=5)
    assert isinstance(report, Report)
    assert isinstance(report.findings, list)
    # 収集された観測量に基本キーが含まれる
    assert "gap" in report.metrics
    assert "nodes" in report.metrics
    assert report.metrics["nodes"] >= 0
    # summary は文字列を返す
    assert isinstance(report.summary(), str)
    # 各 finding は診断ルールの必須フィールドを持つ
    for f in report.findings:
        assert {"id", "severity", "symptom", "recommendation"} <= set(f)
