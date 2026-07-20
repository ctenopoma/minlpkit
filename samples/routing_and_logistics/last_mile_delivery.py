"""ラストマイル配送ルート最適化 (Last-mile Delivery).

配送センターの配車担当者が、当日の複数配送先を1台(または少数)の車両で
巡回する順序を、積載量制約を守りながら総移動コストが最小になるように決める
車両ルーティング問題である。各配送先には荷物量(需要)があり、車両には積載容量の
上限があるため、単純な巡回セールスマン問題と異なり「容量を超えない範囲で
どの順に回るか」という制約が加わる。デポ発着・全顧客訪問・容量遵守を同時に満たす
経路は自明ではなく、MTZ型の部分巡回除去制約が必要になる。

scale ノブ:
    small   : 顧客4 (デポ含め5ノード、テスト用)
    default : 顧客6
    large   : 顧客9
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_cust=4),
    "default": dict(n_cust=6),
    "large":   dict(n_cust=9),
}

VEHICLE_CAP = 400.0  # 単一車両が全顧客を1周で回りきれるよう需要合計を上回る容量に設定


def _data(scale: str):
    cfg = SCALES[scale]
    nC = cfg["n_cust"]
    rng = np.random.default_rng(20260724 + nC * 17)
    n = nC + 1  # ノード0はデポ
    coord = rng.uniform(0.0, 50.0, size=(n, 2))
    coord[0] = [25.0, 25.0]
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            dist[i, j] = np.hypot(*(coord[i] - coord[j]))
    demand = np.zeros(n)
    demand[1:] = rng.uniform(15.0, 30.0, nC)
    return dict(n=n, nC=nC, dist=dist, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    n, dist, demand = d["n"], d["dist"], d["demand"]

    model = Model("Last_Mile_Delivery")
    NODES = range(n)

    x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in NODES for j in NODES if i != j}
    # MTZ部分巡回除去用の累積搭載量(デポ出発時からその地点までの累積配達量)
    u = {i: model.addVar(vtype="C", lb=float(demand[i]), ub=VEHICLE_CAP, name=f"u_{i}")
         for i in NODES if i != 0}

    for i in NODES:
        model.addCons(quicksum(x[i, j] for j in NODES if i != j) == 1, name=f"out_{i}")
        model.addCons(quicksum(x[j, i] for j in NODES if i != j) == 1, name=f"in_{i}")

    for i in NODES:
        if i == 0:
            continue
        for j in NODES:
            if j == 0 or j == i:
                continue
            # MTZ制約: 容量制約と部分巡回除去を同時に表現
            model.addCons(
                u[j] >= u[i] + float(demand[j]) - VEHICLE_CAP * (1 - x[i, j]),
                name=f"mtz_{i}_{j}")

    model.setObjective(
        quicksum(x[i, j] * float(dist[i, j]) for i in NODES for j in NODES if i != j),
        "minimize")
    model.data = {"x": x, "u": u, "scale": scale, "dims": (n,)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
