"""物理要素を横断結合した統合 MINLP サンプル2本の smoke テスト。

対象:
  - plant_utility_integrated_minlp       (熱交換LMTD × 流量/ポンプ相似則 × 外気温依存COP
                                          × 成層蓄熱 × 蓄電池劣化)
  - train_schedule_battery_grid_minlp    (列車ダイヤ × 車載蓄電池SOC × 直流き電網潮流)

いずれも対数・3次有理式・P=V·I といった真の非凸を多数含むため、`ac_opf` と同じ方針で
**最適性証明は求めない**。受け入れ基準は「時間制限内に実行可能解が出て目的値が有限」。
モックは使わず実 SCIP で解く。
"""
from __future__ import annotations

import math

import plant_utility_integrated_minlp as plant
import train_schedule_battery_grid_minlp as train


def _solve_small(mod, seconds: float):
    m = mod.build_model("small")
    m.hideOutput()
    m.setParam("limits/time", seconds)
    m.optimize()
    return m


def test_plant_small_feasible_finite():
    """統合プラント: small で実行可能解が出て運転費が有限かつ正であること。"""
    m = _solve_small(plant, 120.0)
    assert m.getNSols() > 0, "plant: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj) and obj > 0.0, f"plant: 目的値が不正 ({obj})"


def test_plant_lmtd_identity_holds():
    """得られた解が対数平均温度差の厳密な定義式を満たすこと(定式化の正しさの検証)。

    `lmtd * (ln dt1 − ln dt2) == dt1 − dt2` を解から直接再計算し、
    幾何平均 <= LMTD <= 算術平均 の古典的不等式も併せて確認する。
    """
    m = _solve_small(plant, 120.0)
    assert m.getNSols() > 0
    d = m.data
    _, nT, _ = d["dims"]
    for t in range(nT):
        dt1 = m.getVal(d["T_hot"][t]) - m.getVal(d["T_ssup"][t])
        dt2 = m.getVal(d["T_pret"][t]) - m.getVal(d["T_cret"][t])
        assert dt1 > dt2 > 0.0, f"plant[t={t}]: dt1 > dt2 > 0 が崩れている"
        lmtd = m.getVal(d["lmtd"][t])
        exact = (dt1 - dt2) / math.log(dt1 / dt2)
        assert abs(lmtd - exact) < 1e-4, f"plant[t={t}]: LMTD が定義式とずれる ({lmtd} vs {exact})"
        # 幾何平均 <= LMTD <= 算術平均
        assert math.sqrt(dt1 * dt2) - 1e-6 <= lmtd <= 0.5 * (dt1 + dt2) + 1e-6


def test_plant_tank_stays_stratified_and_restored():
    """蓄熱槽が成層を保ち(上層ほど高温)、期末に初期蓄熱量まで回復していること。"""
    m = _solve_small(plant, 120.0)
    assert m.getNSols() > 0
    d = m.data
    _, nT, nL = d["dims"]
    T_lay = d["T_lay"]
    for t in range(nT + 1):
        temps = [m.getVal(T_lay[l, t]) for l in range(nL)]
        for l in range(nL - 1):
            assert temps[l] >= temps[l + 1] - 1e-4, \
                f"plant[t={t}]: 温度成層が逆転している {temps}"
    init = sum(m.getVal(T_lay[l, 0]) for l in range(nL))
    term = sum(m.getVal(T_lay[l, nT]) for l in range(nL))
    assert term >= init - 1e-3, "plant: 期末の蓄熱量が初期を下回っている"


def test_train_small_feasible_finite():
    """列車統合モデル: small で実行可能解が出て総費用が有限かつ正であること。"""
    m = _solve_small(train, 150.0)
    assert m.getNSols() > 0, "train: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj) and obj > 0.0, f"train: 目的値が不正 ({obj})"


def test_train_schedule_and_soc_are_consistent():
    """各列車が各駅をちょうど1回発車し、SOCが窓内に収まり期末条件を満たすこと。"""
    m = _solve_small(train, 150.0)
    assert m.getNSols() > 0
    d = m.data
    nI, nS, nT, _ = d["dims"]
    x, choices = d["x"], d["dep_choices"]
    for i in range(nI):
        for s in range(nS - 1):
            chosen = sum(round(m.getVal(x[i, s, mn, tau])) for mn, tau in choices[i, s])
            assert chosen == 1, f"train: 列車{i} 駅{s} の発車が {chosen} 回"
    soc = d["soc"]
    lo = train.SOC_MIN_FRAC * train.BATT_CAP
    hi = train.SOC_MAX_FRAC * train.BATT_CAP
    for i in range(nI):
        for t in range(nT + 1):
            v = m.getVal(soc[i, t])
            assert lo - 1e-4 <= v <= hi + 1e-4, f"train: 列車{i} t={t} のSOCが窓外 ({v})"
        assert m.getVal(soc[i, nT]) >= train.SOC_TERM_FRAC * train.BATT_CAP - 1e-4


def test_train_schedule_freedom_reduces_cost():
    """ダイヤを基準どおりに固定するより、発車時刻を動かせる方が安くなること。

    「発車時刻をずらして回生電力の授受を成立させる」という本モデルの主張そのものの検証。
    固定側は最適化側の実行可能領域の部分集合なので、この不等式は定式化上必ず成り立つ
    (ここでは打ち切り時の実行可能解どうしの比較なので、ゆるめの許容差で確認する)。
    """
    free = _solve_small(train, 150.0)
    assert free.getNSols() > 0

    fixed = train.build_model("small")
    fixed.hideOutput()
    fixed.setParam("limits/time", 150.0)
    x, choices, nominal = fixed.data["x"], fixed.data["dep_choices"], fixed.data["nominal"]
    for (i, s), cs in choices.items():
        for mn, tau in cs:
            if tau != int(nominal[i, s]):
                fixed.chgVarUb(x[i, s, mn, tau], 0.0)
    fixed.optimize()
    assert fixed.getNSols() > 0, "train: ダイヤ固定版で実行可能解なし"

    assert free.getObjVal() <= fixed.getObjVal() + 1e-3, \
        f"train: ダイヤ最適化が固定より悪化 ({free.getObjVal()} > {fixed.getObjVal()})"


def test_scales_build_with_nonlinear_and_discrete_structure():
    """両モデルとも3スケールで build でき、離散変数と非線形制約を含むこと。"""
    for mod, name in ((plant, "plant"), (train, "train")):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0 and m.getNConss() > 0
            n_bin = sum(1 for v in m.getVars() if v.vtype() == "BINARY")
            assert n_bin > 0, f"{name}[{sc}]: バイナリ変数がない"
            n_nl = sum(1 for c in m.getConss()
                       if c.getConshdlrName() in ("nonlinear", "quadratic", "abspower"))
            assert n_nl > 0, f"{name}[{sc}]: 非線形制約がない"
