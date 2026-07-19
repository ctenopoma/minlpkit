"""多階層物流ネットワーク配送計画 (Multi-echelon Distribution)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Multi_Echelon_Distribution")
    # 工場 -> 倉庫 -> 顧客
    x1 = model.addVar(vtype="C", lb=0, name="x1")
    x2 = model.addVar(vtype="C", lb=0, name="x2")
    model.addCons(x1 >= 50, "factory_output")
    model.addCons(x2 == x1, "warehouse_flow")
    model.setObjective(3 * x1 + 4 * x2, "minimize")
    model.data = {"x1": x1, "x2": x2}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
