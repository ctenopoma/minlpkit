"""ゴミ収集配送ルート最適化 (Waste Collection Routing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Waste_Collection")
    x = {i: model.addVar(vtype="B", name=f"x_{i}") for i in range(4)}
    model.addCons(quicksum(x[i] for i in range(4)) >= 3, "visit_all")
    model.setObjective(quicksum(x[i] * (10 + i * 2) for i in range(4)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Routing cost:", m.getObjVal())
