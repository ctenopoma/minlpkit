"""クロスドッキング拠点のドア割当・仕分け計画 (Cross-docking Scheduling)

事業ストーリー
--------------
3PL倉庫のクロスドック(在庫を持たず入荷トラックから出荷トラックへ即座に積み替える拠点)で、
オペレーション担当者が「どの入荷トラックをどのドアで荷降ろしし、どの出荷トラックをどのドアで
積込みするか」「入荷した各品目をどの出荷便へ何個ずつ仕分けるか」を同時に決める。ドアは限られた
リソースで、割り当てたトラックの荷役時間の合計がシフト内に収まらなければならない
(荷役時間 × 割当数 が資源制約として効く、いわば時間帯付きナップサック)。品目ごとの入荷量と
出荷便ごとの需要量を、ドアの割当と独立に仕分けフロー変数でバランスさせることで、ドア割当と
仕分けが互いに実行可能性を制約し合う構造になっている。
"""

from pyscipopt import Model, quicksum

N_IN, N_OUT, N_DOOR, N_ITEM = 3, 3, 2, 2
SHIFT_LEN = 6.0  # ドア1つあたりのシフト内稼働可能時間 [h]

# 入荷トラック: 荷降ろし所要時間[h]、品目別供給量
UNLOAD_TIME = [1.2, 1.5, 1.0]
SUPPLY = [[40, 20], [15, 35], [25, 10]]  # SUPPLY[i][p]

# 出荷トラック: 積込み所要時間[h]、品目別必要量
LOAD_TIME = [1.0, 1.3, 0.8]
DEMAND = [[30, 25], [20, 20], [25, 15]]  # DEMAND[j][p]

TRANSFER_COST = 2.0  # 仕分けフロー1単位あたりの取扱コスト
DOOR_FIXED_COST = 50.0  # ドア割当1件あたりの固定コスト(段取り)


def build_model():
    model = Model("Cross_Docking")
    IN, OUT, DOOR, ITEM = range(N_IN), range(N_OUT), range(N_DOOR), range(N_ITEM)

    # ドア割当(整数拠点の限られたドアリソースへの二値割当)
    a = {(i, d): model.addVar(vtype="B", name=f"a_{i}_{d}") for i in IN for d in DOOR}
    b = {(j, d): model.addVar(vtype="B", name=f"b_{j}_{d}") for j in OUT for d in DOOR}
    # 品目別 仕分けフロー: 入荷トラックi -> 出荷トラックj へ品目pを移す量
    x = {(i, j, p): model.addVar(vtype="C", lb=0, name=f"x_{i}_{j}_{p}")
         for i in IN for j in OUT for p in ITEM}

    # 各トラックはちょうど1つのドアで処理される
    for i in IN:
        model.addCons(quicksum(a[i, d] for d in DOOR) == 1, f"in_door_{i}")
    for j in OUT:
        model.addCons(quicksum(b[j, d] for d in DOOR) == 1, f"out_door_{j}")

    # ドアの稼働時間はシフト内に収まる(荷降ろし+積込みの合計)
    for d in DOOR:
        model.addCons(
            quicksum(UNLOAD_TIME[i] * a[i, d] for i in IN)
            + quicksum(LOAD_TIME[j] * b[j, d] for j in OUT) <= SHIFT_LEN,
            f"door_capacity_{d}")

    # 供給上限: 入荷トラックiの品目pの出荷先合計は供給量以下
    for i in IN:
        for p in ITEM:
            model.addCons(quicksum(x[i, j, p] for j in OUT) <= SUPPLY[i][p],
                          f"supply_{i}_{p}")

    # 需要充足: 出荷トラックjの品目pの受取合計は需要量以上
    for j in OUT:
        for p in ITEM:
            model.addCons(quicksum(x[i, j, p] for i in IN) >= DEMAND[j][p],
                          f"demand_{j}_{p}")

    door_cost = DOOR_FIXED_COST * (quicksum(a[i, d] for i in IN for d in DOOR)
                                    + quicksum(b[j, d] for j in OUT for d in DOOR))
    transfer_cost = TRANSFER_COST * quicksum(x[i, j, p] for i in IN for j in OUT for p in ITEM)
    model.setObjective(door_cost + transfer_cost, "minimize")

    model.data = {"a": a, "b": b, "x": x}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
