"""実行不可能診断(弾性緩和・削除フィルタ・診断ルール)のテスト。実SCIPで回す。"""
from __future__ import annotations

import sys
from pathlib import Path

from pyscipopt import Model

import minlpkit as mk

sys.path.insert(0, str(Path(__file__).parent.parent / "samples" / "others"))
from infeasible_supply_plan import build_model  # noqa: E402


def _feasible_build() -> Model:
    """実行可能な小モデル(実行不可能判定の陰性ケース)。"""
    m = Model()
    m.hideOutput()
    x = m.addVar("x", lb=0, ub=10)
    y = m.addVar("y", lb=0, ub=10)
    m.addCons(x + y <= 8, name="cap")
    m.addCons(x >= 2, name="minx")
    m.setObjective(x + y, "maximize")
    return m


def test_base_status_detects_infeasible():
    from minlpkit.collectors.infeasibility import base_status
    assert base_status(build_model, time_limit=10) == "infeasible"
    assert base_status(_feasible_build, time_limit=10) == "optimal"


def test_presolve_infeasible_flag():
    """過剰契約は presolve の境界タイト化で矛盾が証明できる。"""
    assert mk.presolve_infeasible(build_model) is True
    assert mk.presolve_infeasible(_feasible_build) is False


def test_deletion_filter_finds_exact_core():
    """削除フィルタは全7本を {cap_total, contract_A/B/C} の4本核へ縮約する。"""
    res = mk.deletion_filter(build_model, time_limit=10)
    assert res["base_status"] == "infeasible"
    core = set(res["core"])
    assert core == {"cap_total", "contract_A", "contract_B", "contract_C"}
    # 充足可能なデコイは核に含まれない
    assert "mix_ratio" not in core and "market_cap_A" not in core and "line_on" not in core


def test_deletion_filter_on_feasible_returns_empty():
    """実行可能モデルでは核は空でnoteに理由が入る。"""
    res = mk.deletion_filter(_feasible_build, time_limit=10)
    assert res["core"] == []
    assert "実行不可能ではない" in res["note"]


def test_elastic_filter_slack_on_culprits_only():
    """弾性緩和のスラックは犯人(能力 or 契約)にだけ立ち、デコイには立たない。"""
    df = mk.elastic_filter(build_model, time_limit=10)
    assert not df.empty
    positive = set(df[df["slack"] > 1e-6]["constraint"])
    # 総違反量は 20(契約合計120 − 能力100)。スラックが立つのは犯人核の制約のみ
    assert positive  # 少なくとも1本
    assert positive <= {"cap_total", "contract_A", "contract_B", "contract_C"}
    decoys = set(df[df["constraint"].isin(["mix_ratio", "market_cap_A", "line_on"])]["slack"].dropna())
    assert all(v <= 1e-6 for v in decoys)
    total_slack = df["slack"].dropna().sum()
    assert abs(total_slack - 20.0) < 1e-4


def test_diagnose_infeasibility_metrics_and_rule():
    """orchestratorのmetricsで infeasible_core ルールが critical で発火する。"""
    res = mk.diagnose_infeasibility(build_model, time_limit=10)
    assert res["infeasible"] is True
    assert res["metrics"]["iis_size"] == 4
    fired = mk.evaluate(res["metrics"])
    hit = [f for f in fired if f["id"] == "infeasible_core"]
    assert hit and hit[0]["severity"] == "critical"


def test_infeasible_core_rule_not_fires_when_feasible():
    """infeasible=False では発火しない。"""
    assert not any(f["id"] == "infeasible_core" for f in mk.evaluate({"infeasible": False}))
    assert not any(f["id"] == "infeasible_core" for f in mk.evaluate({}))
