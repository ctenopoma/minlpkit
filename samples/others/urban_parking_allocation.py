"""都市型スマート駐車場予約割当 (Urban Parking Allocation)

スマート駐車場アプリの運営者が、予約リクエストを出した複数の車両を複数の駐車場
(立地・料金の異なる区画)へ割り当てる意思決定である。各駐車場には収容台数の上限があり、
車両ごとに希望する到着時間帯があるため、同じ時間帯に希望が集中する駐車場では割当を
奪い合う。近い立地・低料金の駐車場ほど車両の効用(満足度)が高いため、全体の効用合計を
最大化しつつ各駐車場の容量と時間帯別の同時収容台数を守る割当を求める。
"""

from pyscipopt import Model, quicksum

VEHICLES = range(6)
LOTS = range(3)
SLOTS = range(2)  # 時間帯(朝・昼)

lot_capacity = {0: 3, 1: 2, 2: 3}
# 車両ごとの希望時間帯(0=朝, 1=昼)
vehicle_slot = {0: 0, 1: 0, 2: 1, 3: 1, 4: 0, 5: 1}
# 効用: 車両と駐車場の相性(立地・料金差を反映した仮想値)
utility = {
    (0, 0): 15, (0, 1): 10, (0, 2): 8,
    (1, 0): 12, (1, 1): 14, (1, 2): 9,
    (2, 0): 9,  (2, 1): 11, (2, 2): 13,
    (3, 0): 14, (3, 1): 8,  (3, 2): 10,
    (4, 0): 11, (4, 1): 13, (4, 2): 12,
    (5, 0): 10, (5, 1): 9,  (5, 2): 15,
}


def build_model():
    model = Model("Urban_Parking")

    x = {(c, l): model.addVar(vtype="B", name=f"x_{c}_{l}") for c in VEHICLES for l in LOTS}

    for c in VEHICLES:
        model.addCons(quicksum(x[c, l] for l in LOTS) <= 1, name=f"assign_once_{c}")

    for l in LOTS:
        for s in SLOTS:
            model.addCons(
                quicksum(x[c, l] for c in VEHICLES if vehicle_slot[c] == s) <= lot_capacity[l],
                name=f"capacity_{l}_{s}",
            )

    model.setObjective(quicksum(x[c, l] * utility[c, l] for c in VEHICLES for l in LOTS), "maximize")
    model.data = {"x": x}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Utility:", m.getObjVal())
