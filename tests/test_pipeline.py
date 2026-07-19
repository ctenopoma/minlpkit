"""pipeline analyze の smoke テスト(facility を実ソルバーで解く)。"""
from __future__ import annotations

import minlpkit as mk
from minlpkit.pipeline import Report


def test_analyze_facility_smoke():
    """facility(線形MILP)で analyze が Report を返し、findings が list になる。"""
    import samples.location_and_network_design.facility as fac

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


def test_analyze_airline_overbooking_no_constraints():
    """制約を1本も持たないモデル(airline_overbooking: 変数境界のみ)でも
    analyze が例外なく Report を返す(linking_constraints の空DataFrame KeyError回帰)。"""
    import samples.scheduling.airline_overbooking as ao

    report = mk.analyze(ao.build_model, name="airline_overbooking", time_limit=5)
    assert isinstance(report, Report)
    assert isinstance(report.findings, list)
    assert isinstance(report.summary(), str)
