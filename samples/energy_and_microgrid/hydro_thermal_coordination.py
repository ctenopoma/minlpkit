"""水火力電源協調運転計画 (Hydro-Thermal Coordination).

電力系統運用者(給電司令)が、複数の火力ユニットと水系(貯水池)の発電計画を
日内複数時間帯にわたって同時に決める起動停止・出力配分問題である。火力ユニットは
起動コストを伴うオン/オフ切替(整数)を持ち、いったん起動すれば最低出力を維持する
必要がある一方、水力は貯水池の総放流量(=発電に使える水資源)という期間を跨いだ
制約に縛られる。各時間帯で「安い水力を優先しつつ、水を使い切らないよう火力で
不足を補う」というトレードオフが、需給バランス・水資源制約・起動ロジックの
組み合わせとして自然に表現される。

scale ノブ:
    small   : 時間帯3 × 火力ユニット2 (テスト用)
    default : 時間帯6 × 火力ユニット3
    large   : 時間帯12 × 火力ユニット4
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_t=3, n_unit=2),
    "default": dict(n_t=6, n_unit=3),
    "large":   dict(n_t=12, n_unit=4),
}

WATER_LIMIT_PER_T = 22.0   # 1時間帯あたり水力の平均放流可能量[MWh]の基準
HYDRO_MAX = 50.0           # 水力の出力上限[MW]
STARTUP_COST = 400.0       # 火力ユニット起動コスト[$]
FUEL_COST_HYDRO = 2.0      # 水力の限界費用[$/MWh](ほぼゼロコスト)


def _data(scale: str):
    cfg = SCALES[scale]
    nT, nU = cfg["n_t"], cfg["n_unit"]
    rng = np.random.default_rng(20260724 + nT * 11 + nU * 7)

    demand = rng.uniform(70.0, 130.0, nT)
    # ユニットごとの定格・最低出力・限界費用(大型ほど安いが最低出力が高い)
    cap = np.array([40.0 + 25.0 * u for u in range(nU)])
    pmin = 0.3 * cap
    mc = np.array([28.0 - 1.5 * u for u in range(nU)])
    water_limit = WATER_LIMIT_PER_T * nT

    return dict(nT=nT, nU=nU, demand=demand, cap=cap, pmin=pmin, mc=mc,
                water_limit=water_limit)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nT, nU = d["nT"], d["nU"]
    demand, cap, pmin, mc, water_limit = d["demand"], d["cap"], d["pmin"], d["mc"], d["water_limit"]

    model = Model("Hydro_Thermal_Coordination")
    T, U = range(nT), range(nU)

    p_hydro = {t: model.addVar(vtype="C", lb=0.0, ub=HYDRO_MAX, name=f"ph_{t}") for t in T}
    p_th = {(t, u): model.addVar(vtype="C", lb=0.0, ub=float(cap[u]), name=f"pt_{t}_{u}")
            for t in T for u in U}
    on = {(t, u): model.addVar(vtype="B", name=f"on_{t}_{u}") for t in T for u in U}
    startup = {(t, u): model.addVar(vtype="B", name=f"su_{t}_{u}") for t in T for u in U}

    for t in T:
        # 需給バランス
        model.addCons(
            p_hydro[t] + quicksum(p_th[t, u] for u in U) >= float(demand[t]),
            name=f"demand_{t}")
        for u in U:
            # 出力はオン/オフに連動(最低・最大出力)
            model.addCons(p_th[t, u] <= on[t, u] * float(cap[u]), name=f"cap_{t}_{u}")
            model.addCons(p_th[t, u] >= on[t, u] * float(pmin[u]), name=f"pmin_{t}_{u}")

    for u in U:
        for t in T:
            prev_on = on[t - 1, u] if t > 0 else 0
            # 起動フラグ: オフ→オンの遷移でのみ 1 になり得る
            model.addCons(startup[t, u] >= on[t, u] - prev_on, name=f"startup_{t}_{u}")

    # 水資源制約: 発電計画期間全体で使える放流量(=水力発電量の総和)に上限
    model.addCons(quicksum(p_hydro[t] for t in T) <= water_limit, name="water_limit")

    fuel_cost = quicksum(float(mc[u]) * p_th[t, u] for t in T for u in U)
    hydro_cost = quicksum(FUEL_COST_HYDRO * p_hydro[t] for t in T)
    startup_total = quicksum(STARTUP_COST * startup[t, u] for t in T for u in U)
    model.setObjective(fuel_cost + hydro_cost + startup_total, "minimize")

    model.data = {"p_hydro": p_hydro, "p_th": p_th, "on": on, "startup": startup,
                  "scale": scale, "dims": (nT, nU)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
