"""ベンダーズ分解 (Phase 6, 2.d)

施設配置(facility)を主問題/サブ問題に分解する:
  主問題(master): 施設の開設 y_i(整数)+ 輸送費の下界近似 η を決める
  サブ問題(sub):  開設 ŷ を固定した輸送LP(連続)。双対から最適性カットを主問題へ返す

    full: min Σf_i y_i + Σc_ij x_ij
          s.t. Σ_i x_ij >= d_j, Σ_j x_ij <= cap_i y_i, Σy_i<=N, y∈{0,1}

サブ問題の値 Q(y) は y の凸関数。その劣勾配(容量制約の双対×cap)で
    η >= Q(ŷ) + Σ_i g_i (y_i − ŷ_i)
の最適性カットを追加していく。総容量>=総需要の集約カットを主問題に入れておくと
サブ問題は常に実行可能になり、実行可能性カットは不要。

サブ問題の双対は scipy.linprog で確実に取得(PySCIPOptの双対取得はpresolveで不安定)。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from pyscipopt import Model, quicksum
from scipy.optimize import linprog

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "samples"))

import facility as fac

FAC = list(fac.FACILITIES)          # 施設
CUST = list(fac.DEMAND)             # 顧客
CAP = {i: fac.FACILITIES[i]["cap"] for i in FAC}
FIXED = {i: fac.FACILITIES[i]["fixed"] for i in FAC}
DEM = dict(fac.DEMAND)
COST = dict(fac.COST)
N_OPEN = fac.N_OPEN_MAX


def solve_subproblem(y_hat: dict) -> tuple[float, dict]:
    """開設 ŷ を固定した輸送LP。(輸送費 Q, 容量制約の劣勾配 g_i) を返す。"""
    nf, nc = len(FAC), len(CUST)
    # 変数 x_ij を (i,j) の順で平坦化
    idx = {(i, j): k for k, (i, j) in enumerate([(i, j) for i in FAC for j in CUST])}
    c = np.array([COST[i, j] for i in FAC for j in CUST], dtype=float)

    rows, b = [], []
    # 需要 Σ_i x_ij >= d_j  →  -Σ_i x_ij <= -d_j
    for j in CUST:
        row = np.zeros(nf * nc)
        for i in FAC:
            row[idx[i, j]] = -1.0
        rows.append(row); b.append(-DEM[j])
    # 容量 Σ_j x_ij <= cap_i ŷ_i
    cap_row_start = len(rows)
    for i in FAC:
        row = np.zeros(nf * nc)
        for j in CUST:
            row[idx[i, j]] = 1.0
        rows.append(row); b.append(CAP[i] * y_hat[i])

    res = linprog(c, A_ub=np.array(rows), b_ub=np.array(b), bounds=(0, None), method="highs")
    Q = float(res.fun)
    marg = res.ineqlin.marginals  # <= 制約の限界価格(<=0)
    # 容量制約 i の劣勾配 g_i = (∂Q/∂b_cap_i)·cap_i = marginal_cap_i · cap_i
    g = {i: float(marg[cap_row_start + k]) * CAP[i] for k, i in enumerate(FAC)}
    return Q, g


def build_master(cuts: list[dict]) -> Model:
    """主問題: min Σf_i y_i + η, 開設上限, 総容量>=総需要, 追加された最適性カット。"""
    m = Model("benders_master")
    y = {i: m.addVar(vtype="B", name=f"y_{i}") for i in FAC}
    eta = m.addVar(lb=0, name="eta")
    m.addCons(quicksum(y[i] for i in FAC) <= N_OPEN, name="open_limit")
    # サブ問題を常に実行可能にする集約カット(総容量>=総需要)
    m.addCons(quicksum(CAP[i] * y[i] for i in FAC) >= sum(DEM.values()), name="feasibility")
    # 最適性カット: η >= Q(ŷ) + Σ_i g_i (y_i − ŷ_i)
    for c in cuts:
        m.addCons(eta >= c["Q"] + quicksum(c["g"][i] * (y[i] - c["yhat"][i]) for i in FAC),
                  name=f"optcut_{c['k']}")
    m.setObjective(quicksum(FIXED[i] * y[i] for i in FAC) + eta, "minimize")
    m.data = dict(y=y, eta=eta)
    return m


def benders(max_iter: int = 30, tol: float = 1e-6) -> dict:
    """ベンダーズ反復。history(LB/UB)と最終解を返す。"""
    cuts: list[dict] = []
    best_ub, best_y = float("inf"), None
    history = []
    for it in range(max_iter):
        m = build_master(cuts)
        m.hideOutput()
        m.optimize()
        y_hat = {i: 1 if m.getVal(m.data["y"][i]) > 0.5 else 0 for i in FAC}
        lb = m.getObjVal()  # 主問題の目的 = 大域下界

        Q, g = solve_subproblem(y_hat)
        ub = sum(FIXED[i] * y_hat[i] for i in FAC) + Q  # この ŷ での真の総費用
        if ub < best_ub:
            best_ub, best_y = ub, y_hat
        history.append(dict(iter=it, lb=lb, ub=best_ub, gap=best_ub - lb))
        if best_ub - lb <= tol:
            break
        cuts.append(dict(k=it, Q=Q, g=g, yhat=y_hat))
    return dict(lb=lb, ub=best_ub, best_y=best_y, history=history, n_cuts=len(cuts))


def monolithic_optimum() -> float:
    m = fac.build_model(infeasible=False)
    m.hideOutput()
    m.optimize()
    return m.getObjVal()
