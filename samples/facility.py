"""容量制約付き施設配置 (MILP, 純粋に線形)

線形IIS・スラック(拘束制約)可視化の検証用モデル。非線形項を持たず、
制約はすべて線形なので presolve 後も線形制約が残る。

    min  Σ f_i y_i + Σ c_ij x_ij
    s.t. Σ_i x_ij >= d_j            (需要充足 / demand_j)
         Σ_j x_ij <= cap_i y_i      (容量 / capacity_i)
         Σ_i y_i <= n_open_max      (開設上限 / open_limit)
         x_ij >= 0, y_i ∈ {0,1}

build_model(infeasible=False) で実行可能、True で需要 > 総容量の不能モデル(IIS検証用)。
"""

from __future__ import annotations

from pyscipopt import Model, quicksum

# 施設 i: (固定費, 容量)
FACILITIES = {
    "F1": dict(fixed=100, cap=60),
    "F2": dict(fixed=120, cap=80),
    "F3": dict(fixed=90,  cap=50),
    "F4": dict(fixed=150, cap=100),
}
# 顧客 j: 需要
DEMAND = {"C1": 40, "C2": 55, "C3": 35, "C4": 60, "C5": 30}
# 輸送費 c_ij
COST = {
    ("F1", "C1"): 4, ("F1", "C2"): 6, ("F1", "C3"): 9, ("F1", "C4"): 8, ("F1", "C5"): 7,
    ("F2", "C1"): 5, ("F2", "C2"): 4, ("F2", "C3"): 7, ("F2", "C4"): 6, ("F2", "C5"): 8,
    ("F3", "C1"): 8, ("F3", "C2"): 7, ("F3", "C3"): 4, ("F3", "C4"): 9, ("F3", "C5"): 5,
    ("F4", "C1"): 6, ("F4", "C2"): 5, ("F4", "C3"): 6, ("F4", "C4"): 4, ("F4", "C5"): 6,
}
N_OPEN_MAX = 3  # 開設上限(拘束させて binding にする)


def constraint_names(infeasible: bool = False) -> list[str]:
    """このモデルが持つ線形制約名の一覧(IISの削除フィルタで列挙に使う)。"""
    return ([f"demand_{j}" for j in DEMAND]
            + [f"capacity_{i}" for i in FACILITIES] + ["open_limit"])


def build_model(infeasible: bool = False, active_cons: set[str] | None = None) -> Model:
    """active_cons=None なら全制約。集合を渡すとその名前の制約だけ張る(IIS用)。"""
    m = Model("facility_location")
    demand = dict(DEMAND)
    if infeasible:
        # 総需要 > 総容量 になるよう C4 の需要を吊り上げ → 実行不能
        demand = {**demand, "C4": 260}

    def use(name: str) -> bool:
        return active_cons is None or name in active_cons

    y = {i: m.addVar(vtype="B", name=f"y_{i}") for i in FACILITIES}
    x = {(i, j): m.addVar(lb=0, name=f"x_{i}_{j}") for i in FACILITIES for j in demand}

    for j in demand:
        if use(f"demand_{j}"):
            m.addCons(quicksum(x[i, j] for i in FACILITIES) >= demand[j], name=f"demand_{j}")
    for i, fac in FACILITIES.items():
        if use(f"capacity_{i}"):
            m.addCons(quicksum(x[i, j] for j in demand) <= fac["cap"] * y[i], name=f"capacity_{i}")
    if use("open_limit"):
        m.addCons(quicksum(y[i] for i in FACILITIES) <= N_OPEN_MAX, name="open_limit")

    m.setObjective(
        quicksum(FACILITIES[i]["fixed"] * y[i] for i in FACILITIES)
        + quicksum(COST[i, j] * x[i, j] for i in FACILITIES for j in demand),
        "minimize")
    m.data = dict(x=x, y=y, demand=demand)
    return m


def main() -> None:
    m = build_model()
    m.optimize()
    print(f"status={m.getStatus()}  obj={m.getObjVal():.1f}")
    y = m.data["y"]
    opened = [i for i in FACILITIES if m.getVal(y[i]) > 0.5]
    print("opened facilities:", opened)


if __name__ == "__main__":
    main()
