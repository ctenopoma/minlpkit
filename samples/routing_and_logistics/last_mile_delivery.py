"""ラストマイル配送ルート最適化 (Last-mile Delivery)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Last_Mile_Delivery")
    NODES = [0, 1, 2] # 0はデポ
    x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in NODES for j in NODES if i != j}
    for i in NODES:
        model.addCons(quicksum(x[i, j] for j in NODES if i != j) == 1, f"out_{i}")
        model.addCons(quicksum(x[j, i] for j in NODES if i != j) == 1, f"in_{i}")
    model.setObjective(quicksum(x[i, j] * 5 for i in NODES for j in NODES if i != j), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
