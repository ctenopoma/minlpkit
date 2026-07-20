"""時間枠付き配送計画問題 (Vehicle Routing with Time Windows)

配送センターのルート計画担当者が、1台の車両が複数の顧客を巡回する順序と各顧客への
到着時刻を、顧客ごとに指定された配送時間枠(この時間帯にしか受け取れない)を守りながら
決める意思決定である。区間ごとの走行時間は固定だが、どの顧客を先に訪問するかによって
後続顧客の到着時刻が変わり、時間枠を外れると再訪問や別便が必要になる。訪問順序の
0-1判断(どちらを先に訪るか)と到着時刻の連続決定が結合するため、単純な時間枠制約だけでは
なく順序選択そのものを最適化する必要がある。
"""

from pyscipopt import Model, quicksum

CUSTOMERS = range(4)
# 区間走行時間[分](対称)
travel_time = {
    (0, 1): 5, (0, 2): 8, (0, 3): 6,
    (1, 2): 4, (1, 3): 7,
    (2, 3): 5,
}
time_window = {0: (0, 10), 1: (5, 20), 2: (10, 30), 3: (15, 35)}
BIG_M = 100.0


def _tt(i, j):
    return travel_time[(i, j)] if i < j else travel_time[(j, i)]


def build_model():
    model = Model("VRP_Time_Windows")

    t = {i: model.addVar(vtype="C", lb=time_window[i][0], ub=time_window[i][1], name=f"t_{i}")
         for i in CUSTOMERS}
    # order[i, j] = 1 なら顧客iを顧客jより先に訪問する
    order = {(i, j): model.addVar(vtype="B", name=f"order_{i}_{j}")
             for i in CUSTOMERS for j in CUSTOMERS if i < j}

    for i in CUSTOMERS:
        for j in CUSTOMERS:
            if i >= j:
                continue
            # どちらか一方の順序のみが成立する(big-Mによる互いに排他な到着時刻制約)
            model.addCons(t[j] >= t[i] + _tt(i, j) - BIG_M * (1 - order[i, j]), name=f"seq_{i}_{j}_fwd")
            model.addCons(t[i] >= t[j] + _tt(i, j) - BIG_M * order[i, j], name=f"seq_{i}_{j}_bwd")

    model.setObjective(quicksum(t[i] for i in CUSTOMERS), "minimize")
    model.data = {"t": t, "order": order}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Total time:", m.getObjVal())
