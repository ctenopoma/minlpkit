"""run 条件キャプチャの正当性テスト(実 SCIP)。

fingerprint(変数/制約の型別内訳)と scip_params_diff(非デフォルト差分)が
実モデルに対して正しく出ることを確認する。
"""
from __future__ import annotations

from pyscipopt import SCIP_PARAMSETTING, Model

from minlpkit.live import capture_run_conditions


def test_fingerprint_counts_by_type():
    """自作の小モデルで変数/制約の型別内訳と目的の向きが正しく数えられる。"""
    m = Model()
    b = m.addVar(vtype="B", name="b")
    i = m.addVar(vtype="I", name="i", lb=0, ub=10)
    x = m.addVar(vtype="C", name="x", lb=0, ub=10)
    y = m.addVar(vtype="C", name="y", lb=0, ub=10)
    m.addCons(b + i + x <= 5)          # 線形
    m.addCons(x * y + i <= 8)          # 非線形(双線形)
    m.setObjective(x + y, sense="maximize")

    cap = capture_run_conditions(m)
    fp = cap["fingerprint"]
    assert fp["n_vars"] == 4
    assert fp["n_bin"] == 1
    assert fp["n_int"] == 1
    assert fp["n_cont"] == 2
    assert fp["objective_sense"] == "maximize"
    # 制約は線形1・非線形1。合計は total と一致
    assert fp["n_conss"] == fp["n_linear"] + fp["n_nonlinear"]
    assert fp["n_nonlinear"] >= 1
    assert fp["n_linear"] >= 1


def test_params_diff_reflects_setparam():
    """setParam で変えた値だけが scip_params_diff に現れ、量が過大でない。"""
    m = Model()
    m.addVar(vtype="B")
    m.setParam("limits/time", 7.0)
    m.setParam("limits/gap", 0.05)

    diff = capture_run_conditions(m)["scip_params_diff"]
    assert diff["limits/time"] == 7.0
    assert diff["limits/gap"] == 0.05
    # デフォルトのままのパラメータは含まれない(差分が数個〜数十個に収まる)
    assert len(diff) < 100
    assert "branching/scorefac" not in diff


def test_params_diff_captures_heuristics_off():
    """setHeuristics(OFF) が差分に反映される(非デフォルト設定を残せる)。"""
    m = Model()
    m.addVar(vtype="B")
    m.setHeuristics(SCIP_PARAMSETTING.OFF)

    diff = capture_run_conditions(m)["scip_params_diff"]
    # ヒューリスティクス freq が無効化(-1)されて多数入る
    freq_off = [k for k, v in diff.items() if k.startswith("heuristics/") and v == -1]
    assert len(freq_off) >= 1


def test_env_and_git_keys_present():
    """env は必須キーを持ち、git_sha は取れれば文字列(取れなければ欠落)。"""
    m = Model()
    cap = capture_run_conditions(m)
    env = cap["env"]
    assert "python" in env
    assert "scip" in env
    assert "os" in env
    # git_sha は取得できた場合のみキーが存在し、その値は文字列
    if "git_sha" in cap:
        assert isinstance(cap["git_sha"], str)
        assert len(cap["git_sha"]) >= 7
