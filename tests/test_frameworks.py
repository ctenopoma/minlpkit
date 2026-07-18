"""frameworks の実ソルバーテスト: column_generation / price_and_branch / benders。

pricing・サブ問題は PySCIPOpt / scipy.linprog を実際に回す。モックなし。
"""
from __future__ import annotations

import math

import numpy as np
import minlpkit as mk
from pyscipopt import Model, quicksum
from scipy.optimize import linprog

# ---- 小 cutting stock ----
# ロール幅 W=10、品目幅 [3,4,5]、需要 [3,3,3]。
WIDTHS = [3, 4, 5]
DEMANDS = [3, 3, 3]
W = 10


def _knapsack_pricing(duals):
    """価格付けナップサック: max Σπ_i a_i s.t. Σ w_i a_i <= W。(列, 値)を返す(実SCIP)。"""
    m = Model("pricing")
    a = {i: m.addVar(vtype="I", lb=0, ub=W // WIDTHS[i], name=f"a_{i}")
         for i in range(len(WIDTHS))}
    m.addCons(quicksum(WIDTHS[i] * a[i] for i in range(len(WIDTHS))) <= W)
    m.setObjective(quicksum(duals[i] * a[i] for i in range(len(WIDTHS))), "maximize")
    m.hideOutput()
    m.optimize()
    col = [int(round(m.getVal(a[i]))) for i in range(len(WIDTHS))]
    return col, m.getObjVal()


def _init_columns():
    # 各品目を単独で詰めた実行可能な初期基底列
    return [[W // WIDTHS[i] if k == i else 0 for i in range(len(WIDTHS))]
            for k in range(len(WIDTHS))]


def test_column_generation_reaches_material_bound():
    """列生成の LP 境界が材料下界に到達し、pricing が収束する。"""
    res = mk.column_generation(DEMANDS, _init_columns(), _knapsack_pricing)
    material_lb = sum(WIDTHS[i] * DEMANDS[i] for i in range(len(WIDTHS))) / W
    assert res["lp_bound"] > 0
    # GG の LP 境界は材料下界と同等(下回らない)
    assert res["lp_bound"] >= material_lb - 1e-6
    # 収束時、最終 pricing 値は 1 以下(改善列が尽きた)
    assert res["history"][-1]["pricing_val"] <= 1 + 1e-6


def _all_patterns():
    """このロール幅で実行可能な全パターン(a0,a1,a2)を列挙(小インスタンスなので網羅可)。"""
    pats = []
    for a0 in range(W // WIDTHS[0] + 1):
        for a1 in range(W // WIDTHS[1] + 1):
            for a2 in range(W // WIDTHS[2] + 1):
                if a0 * WIDTHS[0] + a1 * WIDTHS[1] + a2 * WIDTHS[2] <= W and (a0 or a1 or a2):
                    pats.append([a0, a1, a2])
    return pats


def _full_ilp_optimum():
    """全パターン上の整数主問題を直接解いた真の最小ロール本数(最適性の基準)。"""
    pats = _all_patterns()
    m = Model("full_cs_ilp")
    lam = [m.addVar(vtype="I", lb=0, name=f"l{p}") for p in range(len(pats))]
    for i in range(len(WIDTHS)):
        m.addCons(quicksum(pats[p][i] * lam[p] for p in range(len(pats))) >= DEMANDS[i])
    m.setObjective(quicksum(lam), "minimize")
    m.hideOutput()
    m.optimize()
    return m.getObjVal()


def test_price_and_branch_bounds_valid():
    """LP境界と整数解の正当性: LP境界は真の最適以下(妥当な下界)、整数解は上界かつ整数。"""
    res = mk.price_and_branch(DEMANDS, _init_columns(), _knapsack_pricing)
    true_opt = _full_ilp_optimum()               # 全パターン ILP の真の最小ロール本数
    # LP 緩和境界は真の整数最適を上回らない(妥当な下界)
    assert res["lp_bound"] <= true_opt + 1e-6
    assert res["lp_lb"] == math.ceil(res["lp_bound"] - 1e-6)
    # 整数解: 整数で、LP 下界を尊重し、真の最適を下回らない実行可能な上界
    assert abs(res["int_obj"] - round(res["int_obj"])) < 1e-6
    assert res["int_obj"] >= res["lp_lb"] - 1e-6
    assert res["int_obj"] >= true_opt - 1e-6


# ---- 小施設配置(benders vs 単一問題)----
# 施設2、顧客3の容量制約付き配置。
FAC = ["A", "B"]
CUST = ["c1", "c2", "c3"]
FIXED = {"A": 100.0, "B": 120.0}
CAP = {"A": 8.0, "B": 10.0}
DEM = {"c1": 3.0, "c2": 4.0, "c3": 5.0}
COST = {
    ("A", "c1"): 4, ("A", "c2"): 6, ("A", "c3"): 9,
    ("B", "c1"): 5, ("B", "c2"): 4, ("B", "c3"): 3,
}


def _monolithic() -> float:
    m = Model("facility_mono")
    y = {i: m.addVar(vtype="B", name=f"y_{i}") for i in FAC}
    x = {(i, j): m.addVar(lb=0, name=f"x_{i}_{j}") for i in FAC for j in CUST}
    for j in CUST:
        m.addCons(quicksum(x[i, j] for i in FAC) >= DEM[j])
    for i in FAC:
        m.addCons(quicksum(x[i, j] for j in CUST) <= CAP[i] * y[i])
    m.setObjective(quicksum(FIXED[i] * y[i] for i in FAC)
                   + quicksum(COST[i, j] * x[i, j] for i in FAC for j in CUST), "minimize")
    m.hideOutput()
    m.optimize()
    return m.getObjVal()


def _subproblem_solve(y_hat: dict):
    """開設 ŷ を固定した輸送LP。(輸送費 Q, 容量制約の劣勾配 grad) を返す(scipy)。"""
    pairs = [(i, j) for i in FAC for j in CUST]
    idx = {p: k for k, p in enumerate(pairs)}
    c = np.array([COST[i, j] for (i, j) in pairs], dtype=float)
    rows, b = [], []
    for j in CUST:  # 需要 Σ_i x_ij >= d_j  →  -Σ x <= -d
        row = np.zeros(len(pairs))
        for i in FAC:
            row[idx[i, j]] = -1.0
        rows.append(row); b.append(-DEM[j])
    cap_start = len(rows)
    for i in FAC:  # 容量 Σ_j x_ij <= cap_i ŷ_i
        row = np.zeros(len(pairs))
        for j in CUST:
            row[idx[i, j]] = 1.0
        rows.append(row); b.append(CAP[i] * y_hat[i])
    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(b), bounds=(0, None), method="highs")
    Q = float(res.fun)
    marg = res.ineqlin.marginals
    grad = {i: float(marg[cap_start + k]) * CAP[i] for k, i in enumerate(FAC)}
    return Q, grad


def _master_build(cuts):
    m = Model("facility_master")
    y = {i: m.addVar(vtype="B", name=f"y_{i}") for i in FAC}
    eta = m.addVar(lb=0, name="eta")
    # サブ問題を常に実行可能にする集約カット(総容量>=総需要)
    m.addCons(quicksum(CAP[i] * y[i] for i in FAC) >= sum(DEM.values()))
    for k, cut in enumerate(cuts):
        m.addCons(eta >= cut["Q"] + quicksum(cut["grad"][i] * (y[i] - cut["yhat"][i])
                                             for i in FAC), name=f"optcut_{k}")
    m.setObjective(quicksum(FIXED[i] * y[i] for i in FAC) + eta, "minimize")
    m.hideOutput()
    m.data = dict(y=y, eta=eta)
    return m


def test_benders_matches_monolithic():
    """汎用ベンダーズの最適値が単一問題の最適値と一致する。"""
    mono = _monolithic()
    res = mk.benders(_master_build, _subproblem_solve)
    assert abs(res["ub"] - mono) < 1e-4
    assert res["ub"] - res["lb"] <= 1e-4       # 下界と上界が収束
    assert res["best_y"] is not None
