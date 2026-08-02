"""campaign(ablate / scenario_sweep / auto_groups)のテスト(実SCIPで求解)。"""
from __future__ import annotations

import json

from pyscipopt import Model

from minlpkit.live import ablate, auto_groups, scenario_sweep, sweep


def build_infeasible():
    """demand_min と cap_max が矛盾する最小モデル(ablate の犯人特定用)。"""
    m = Model()
    m.hideOutput()
    x = m.addVar(lb=0, ub=10, name="x")
    m.addCons(x >= 6, name="demand_min")
    m.addCons(x <= 4, name="cap_max")
    m.setObjective(x, "minimize")
    return m


def test_ablate_finds_conflicting_groups(tmp_path):
    """矛盾モデルの ablate: baseline=infeasible、両群 Off で可解 → critical verdict。"""
    runs = tmp_path / "runs"
    camps = tmp_path / "campaigns"
    df = ablate(build_infeasible, {"demand": "demand", "cap": "cap"},
                name="t_abl", time_limit=5, runs_root=runs, campaigns_root=camps)

    # 先頭行が baseline(off=None)で infeasible
    assert df.iloc[0]["status"] == "infeasible"
    assert json.loads(df.iloc[0]["axis"])["off"] is None
    # 両グループとも「外すと可解」→ 犯人(critical)として verdict が付く
    assert (df["verdict"] != "").sum() == 2

    # campaign.json: kind / members / verdicts が揃う
    cj = json.loads(next(camps.glob("*/campaign.json")).read_text(encoding="utf-8"))
    assert cj["kind"] == "ablation"
    assert len(cj["members"]) == 3
    assert {v["severity"] for v in cj["verdicts"]} == {"critical"}
    assert all({"group", "verdict", "evidence", "recipe"} <= set(v) for v in cj["verdicts"])

    # 各 run の meta.json に campaign(id/kind/axis)が記録される
    meta = json.loads((runs / df.iloc[1]["run_id"] / "meta.json").read_text(encoding="utf-8"))
    assert meta["campaign"]["kind"] == "ablation"
    assert meta["campaign"]["id"] == cj["campaign_id"]
    assert "off" in meta["campaign"]["axis"]


def test_ablate_auto_groups(tmp_path):
    """groups 省略時は制約名の接頭辞から自動グループ化される。"""
    df = ablate(build_infeasible, None, name="t_auto", time_limit=5,
                runs_root=tmp_path / "runs", campaigns_root=tmp_path / "campaigns")
    offs = {json.loads(a)["off"] for a in df["axis"]}
    assert offs == {None, "demand_min", "cap_max"}


def test_auto_groups_strips_indices():
    """インデックス付き制約名(demand_J1 / x_J1_M1 / cap[2,1])が接頭辞に潰れる。"""
    m = Model()
    m.hideOutput()
    x = m.addVar(lb=0, ub=10, name="x")
    m.addCons(x >= 1, name="demand_J1")
    m.addCons(x >= 2, name="demand_J2")
    m.addCons(x <= 9, name="cap[2,1]")
    m.addCons(x <= 8, name="link_a_b")  # 数字なし → そのまま
    assert set(auto_groups(m)) == {"demand", "cap", "link_a_b"}


def test_scenario_sweep_verdicts(tmp_path):
    """入力シナリオ切替: 可行/不可行が axis 付きで記録され、不可行に verdict が付く。"""
    def build(demand):
        m = Model()
        m.hideOutput()
        x = m.addVar(lb=0, ub=5, name="x")
        m.addCons(x >= demand, name="demand")
        m.setObjective(x, "minimize")
        return m

    camps = tmp_path / "campaigns"
    df = scenario_sweep(build, {"low": 2, "over": 9}, name="t_scn", time_limit=5,
                        runs_root=tmp_path / "runs", campaigns_root=camps)
    assert list(df["status"]) == ["optimal", "infeasible"]
    assert df.iloc[1]["verdict"] != ""

    cj = json.loads(next(camps.glob("*/campaign.json")).read_text(encoding="utf-8"))
    assert cj["kind"] == "scenario"
    assert cj["verdicts"][0]["group"] == "over"
    assert cj["verdicts"][0]["severity"] == "critical"


def test_sweep_writes_campaign(tmp_path):
    """既存の sweep も campaign(kind=sweep)として記録され、最良パラメータ verdict が付く。"""
    from pyscipopt import quicksum

    def build():
        m = Model()
        m.hideOutput()
        x = {i: m.addVar(vtype="B", name=f"x{i}") for i in range(6)}
        m.addCons(quicksum(x.values()) <= 3)
        m.setObjective(quicksum((i + 1) * x[i] for i in x), "maximize")
        return m

    runs = tmp_path / "runs"
    df = sweep(build, [{"limits/gap": 0.0}, {"limits/gap": 0.5}],
               name="t_sw", time_limit=5, runs_root=runs)
    cj = json.loads(next((tmp_path / "campaigns").glob("*/campaign.json"))
                    .read_text(encoding="utf-8"))
    assert cj["kind"] == "sweep"
    assert len(cj["members"]) == 2
    assert cj["verdicts"][0]["severity"] == "good"
    meta = json.loads((runs / df["run_id"][0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["campaign"]["kind"] == "sweep"
