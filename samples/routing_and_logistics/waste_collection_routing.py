"""ゴミ収集配送ルート最適化 (Waste Collection Routing)

自治体の廃棄物収集事業者が、複数の収集拠点(集積所)を複数台の収集車でどう分担して
巡回するかを決める意思決定である。各拠点には推定排出量があり、1台の収集車には積載重量の
上限があるため、拠点をどの車両の担当にするか(0-1の割当)と各車両の総積載量が容量を
超えないことを同時に満たす必要がある。全拠点を必ず収集しなければならない一方、
車両ごとの走行コストは担当する拠点数や距離に依存するため、単純な「訪問するかどうか」
だけでなく「どの車両が担当するか」という割当の組合せが総コストを左右する。
"""

from pyscipopt import Model, quicksum

STOPS = range(6)
VEHICLES = range(2)

waste_amount = {0: 8, 1: 6, 2: 9, 3: 7, 4: 5, 5: 10}
vehicle_capacity = {0: 22, 1: 25}
# 拠点iを車両kが収集する際のコスト(距離・走行時間を反映した仮想値)
collection_cost = {
    (0, 0): 10, (0, 1): 14,
    (1, 0): 12, (1, 1): 9,
    (2, 0): 15, (2, 1): 11,
    (3, 0): 8,  (3, 1): 13,
    (4, 0): 11, (4, 1): 10,
    (5, 0): 16, (5, 1): 12,
}


def build_model():
    model = Model("Waste_Collection")

    x = {(i, k): model.addVar(vtype="B", name=f"x_{i}_{k}") for i in STOPS for k in VEHICLES}

    for i in STOPS:
        model.addCons(quicksum(x[i, k] for k in VEHICLES) == 1, name=f"visit_{i}")

    for k in VEHICLES:
        model.addCons(quicksum(waste_amount[i] * x[i, k] for i in STOPS) <= vehicle_capacity[k],
                       name=f"capacity_{k}")

    model.setObjective(quicksum(collection_cost[i, k] * x[i, k] for i in STOPS for k in VEHICLES), "minimize")
    model.data = {"x": x}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Routing cost:", m.getObjVal())
