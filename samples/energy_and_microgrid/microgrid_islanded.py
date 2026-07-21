"""孤立型マイクログリッド運転計画 (Islanded Microgrid).

離島や災害復旧地域の運転オペレーターが、系統から切り離された(孤立=islanded)
マイクログリッドで、複数台のディーゼル発電機と蓄電池を使って需要を満たす
日内運用計画を決める問題である。系統という無限バックストップが無いため、
発電機の起動停止(整数)・出力配分・蓄電池の充放電を組み合わせて常に需給を
一致させなければならず、発電力が不足する場合のみ計画停電(負荷遮断、高コスト)
で帳尻を合わせる。発電機は起動のたびに燃料消費が増えるコストを伴うため、
「小刻みにオンオフする」より「まとめて稼働させる」方が有利になるトレードオフが
起動コストを通じて自然に表現される。

scale ノブ:
    small   : 発電機2台 × 時刻4 (テスト用)
    default : 発電機3台 × 時刻8
    large   : 発電機4台 × 時刻12
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_gen=2, n_t=4),
    "default": dict(n_gen=3, n_t=8),
    "large":   dict(n_gen=4, n_t=12),
}

SHED_COST = 100.0        # 計画停電(負荷遮断)の単価[$/kWh](高コストのペナルティ)
STARTUP_COST = 60.0      # 発電機の起動コスト[$]
BATT_CAP = 80.0          # 蓄電池容量[kWh]
MAX_CRATE = 0.5          # 蓄電池の最大C-rate
ETA = 0.95               # 充放電効率


def _data(scale: str):
    cfg = SCALES[scale]
    nG, nT = cfg["n_gen"], cfg["n_t"]
    rng = np.random.default_rng(20260724 + nG * 31 + nT * 11)

    demand = rng.uniform(55.0, 90.0, nT)
    gen_cap = np.array([20.0 + 8.0 * g for g in range(nG)])
    gen_min = 0.25 * gen_cap
    mc = np.array([6.0 - 0.4 * g for g in range(nG)])

    return dict(nG=nG, nT=nT, demand=demand, gen_cap=gen_cap, gen_min=gen_min, mc=mc)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nG, nT = d["nG"], d["nT"]
    demand, gen_cap, gen_min, mc = d["demand"], d["gen_cap"], d["gen_min"], d["mc"]

    model = Model("Islanded_Microgrid")
    G, T = range(nG), range(nT)

    gen = {(g, t): model.addVar(vtype="C", lb=0.0, ub=float(gen_cap[g]), name=f"gen_{g}_{t}")
           for g in G for t in T}
    on = {(g, t): model.addVar(vtype="B", name=f"on_{g}_{t}") for g in G for t in T}
    startup = {(g, t): model.addVar(vtype="B", name=f"su_{g}_{t}") for g in G for t in T}
    shed = {t: model.addVar(vtype="C", lb=0.0, name=f"shed_{t}") for t in T}
    charge = {t: model.addVar(vtype="C", lb=0.0, ub=MAX_CRATE * BATT_CAP, name=f"chg_{t}") for t in T}
    discharge = {t: model.addVar(vtype="C", lb=0.0, ub=MAX_CRATE * BATT_CAP, name=f"dis_{t}") for t in T}
    soc = {t: model.addVar(vtype="C", lb=0.0, ub=BATT_CAP, name=f"soc_{t}") for t in range(nT + 1)}

    model.addCons(soc[0] == 0.5 * BATT_CAP, name="soc_init")
    model.addCons(soc[nT] >= 0.5 * BATT_CAP, name="soc_terminal")

    for t in T:
        for g in G:
            model.addCons(gen[g, t] <= on[g, t] * float(gen_cap[g]), name=f"cap_{g}_{t}")
            model.addCons(gen[g, t] >= on[g, t] * float(gen_min[g]), name=f"min_{g}_{t}")
            prev_on = on[g, t - 1] if t > 0 else 0
            model.addCons(startup[g, t] >= on[g, t] - prev_on, name=f"startup_{g}_{t}")

        model.addCons(
            quicksum(gen[g, t] for g in G) + discharge[t] + shed[t]
            == float(demand[t]) + charge[t],
            name=f"balance_{t}")
        model.addCons(
            soc[t + 1] == soc[t] + ETA * charge[t] - discharge[t] / ETA,
            name=f"soc_balance_{t}")

    fuel = quicksum(float(mc[g]) * gen[g, t] for g in G for t in T)
    startup_total = quicksum(STARTUP_COST * startup[g, t] for g in G for t in T)
    shed_total = quicksum(SHED_COST * shed[t] for t in T)
    model.setObjective(fuel + startup_total + shed_total, "minimize")

    model.data = {"gen": gen, "on": on, "shed": shed, "soc": soc,
                  "scale": scale, "dims": (nG, nT)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
