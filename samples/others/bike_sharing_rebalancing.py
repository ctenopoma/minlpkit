"""シェアサイクル再配置ルーティング (Bike Sharing Rebalancing)

事業ストーリー
--------------
シェアサイクル運営会社のオペレーションチームが、夜間にトラックで自転車を運び、
朝の需要ピークに備えてステーション間の在庫を調整する再配置計画を立てる。
通勤駅前ステーションは朝に不足しやすく、住宅街ステーションは余剰になりやすいという
非対称な偏りを、最小コストの車両移動で解消したい。

各制約の業務的意味:
- **各ステーションの需給バランス**: 各ステーションについて「搬出台数 - 搬入台数」が
  そのステーションの余剰・不足量(データとして所与)と一致しなければならない
  (フロー保存則)。
- **経路ごとの搬送量に応じたトラック出動判断(二値変数)**: ある区間で自転車を運ぶには
  トラックをその経路に出動させる必要があり、出動すれば固定の出動コストが発生する
  (台数に依存しない固定費+距離比例の変動費という現実の運搬コスト構造)。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

STATIONS = ["central_station", "uptown_office", "riverside_park", "suburb_residential"]
# 正=余剰(引き取るべき)、負=不足(補充すべき)
IMBALANCE = {
    "central_station": -12,      # 朝の通勤需要で不足
    "uptown_office": -8,
    "riverside_park": 9,         # 夜間利用が少なく余剰
    "suburb_residential": 11,
}
DISTANCE = {
    ("central_station", "uptown_office"): 3, ("uptown_office", "central_station"): 3,
    ("central_station", "riverside_park"): 5, ("riverside_park", "central_station"): 5,
    ("central_station", "suburb_residential"): 7, ("suburb_residential", "central_station"): 7,
    ("uptown_office", "riverside_park"): 6, ("riverside_park", "uptown_office"): 6,
    ("uptown_office", "suburb_residential"): 8, ("suburb_residential", "uptown_office"): 8,
    ("riverside_park", "suburb_residential"): 4, ("suburb_residential", "riverside_park"): 4,
}
VAR_COST_PER_BIKE_KM = 1.5
DISPATCH_FIXED_COST = 20
TRUCK_CAPACITY = 20


def build_model():
    model = Model("Bike_Rebalancing")

    edges = list(DISTANCE.keys())
    move = {(i, j): model.addVar(vtype="I", lb=0, ub=TRUCK_CAPACITY, name=f"move_{i}_{j}")
            for (i, j) in edges}
    use = {(i, j): model.addVar(vtype="B", name=f"use_{i}_{j}") for (i, j) in edges}

    for (i, j) in edges:
        model.addCons(move[i, j] <= TRUCK_CAPACITY * use[i, j], f"link_{i}_{j}")

    for s in STATIONS:
        outflow = quicksum(move[s, j] for j in STATIONS if (s, j) in move)
        inflow = quicksum(move[i, s] for i in STATIONS if (i, s) in move)
        model.addCons(outflow - inflow == IMBALANCE[s], f"balance_{s}")

    var_cost = quicksum(VAR_COST_PER_BIKE_KM * DISTANCE[i, j] * move[i, j] for (i, j) in edges)
    fixed_cost = quicksum(DISPATCH_FIXED_COST * use[i, j] for (i, j) in edges)
    model.setObjective(var_cost + fixed_cost, "minimize")
    model.data = {"move": move, "use": use}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Rebalance Cost:", m.getObjVal())
