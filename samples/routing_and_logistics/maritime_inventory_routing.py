"""海運在庫配送計画問題 (Maritime Inventory Routing).

船舶運航計画者が、複数の受入港(顧客拠点)の在庫水準を許容範囲内に保ちながら、
限られた隻数のタンカーで各港へどの時期にどれだけ荷役(積み下ろし)するかを
決める在庫配送統合問題である。港ごとに消費(出荷)ペースが異なり在庫が自然に
減っていくため、在庫が下限を割る前に補充船を着けなければならない一方、
同時に着岸できる船の数には上限がある(=期あたりの寄港回数という整数決定)。
在庫保管コストと海上輸送コストのトレードオフのもとで、「どの港に・いつ・
何隻を配船するか」を各期の在庫バランス制約とともに同時決定する。

scale ノブ:
    small   : 港2 × 期4 (テスト用)
    default : 港3 × 期6
    large   : 港4 × 期8
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_port=2, n_t=4),
    "default": dict(n_port=3, n_t=6),
    "large":   dict(n_port=4, n_t=8),
}

SHIP_CAP = 40.0          # 1隻あたりの積載量[千トン]
FLEET_SIZE_PER_T = 2     # 各期に同時運航できる隻数上限
HOLDING_COST = 1.2       # 在庫保管コスト[$/千トン/期]
SHIPPING_COST = 20.0     # 1隻あたりの海上輸送コスト[$]


def _data(scale: str):
    cfg = SCALES[scale]
    nP, nT = cfg["n_port"], cfg["n_t"]
    rng = np.random.default_rng(20260724 + nP * 23 + nT * 7)

    consumption = rng.uniform(10.0, 20.0, size=(nP, nT))
    inv_min = rng.uniform(8.0, 15.0, nP)
    inv_max = inv_min + rng.uniform(60.0, 90.0, nP)
    inv0 = inv_min + 0.5 * (inv_max - inv_min)

    return dict(nP=nP, nT=nT, consumption=consumption, inv_min=inv_min,
                inv_max=inv_max, inv0=inv0)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nP, nT = d["nP"], d["nT"]
    consumption, inv_min, inv_max, inv0 = d["consumption"], d["inv_min"], d["inv_max"], d["inv0"]

    model = Model("Maritime_Inventory_Routing")
    P, T = range(nP), range(nT)

    inv = {(i, t): model.addVar(vtype="C", lb=0.0, ub=float(inv_max[i]), name=f"inv_{i}_{t}")
           for i in P for t in T}
    n_ship = {(i, t): model.addVar(vtype="I", lb=0, ub=FLEET_SIZE_PER_T, name=f"nship_{i}_{t}")
              for i in P for t in T}
    q = {(i, t): model.addVar(vtype="C", lb=0.0, name=f"q_{i}_{t}") for i in P for t in T}

    for t in T:
        # 各期の全港合計での同時配船隻数に船隊規模の上限
        model.addCons(quicksum(n_ship[i, t] for i in P) <= FLEET_SIZE_PER_T, name=f"fleet_{t}")
        for i in P:
            model.addCons(q[i, t] <= SHIP_CAP * n_ship[i, t], name=f"ship_cap_{i}_{t}")
            model.addCons(inv[i, t] >= float(inv_min[i]), name=f"inv_min_{i}_{t}")
            prev = inv0[i] if t == 0 else inv[i, t - 1]
            model.addCons(
                inv[i, t] == prev - float(consumption[i, t]) + q[i, t],
                name=f"balance_{i}_{t}")

    holding = quicksum(HOLDING_COST * inv[i, t] for i in P for t in T)
    shipping = quicksum(SHIPPING_COST * n_ship[i, t] for i in P for t in T)
    model.setObjective(holding + shipping, "minimize")
    model.data = {"inv": inv, "q": q, "n_ship": n_ship, "scale": scale, "dims": (nP, nT)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
