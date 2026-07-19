"""射出成形型替え・製造スケジュール (Molded Parts Setup Optimization)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Molded_Parts_Setup")
    # 金型の選択と切り替え
    x = {i: model.addVar(vtype="B", name=f"x_{i}") for i in range(3)}
    model.addCons(quicksum(x[i] for i in range(3)) >= 2, "min_molds")
    model.setObjective(quicksum(x[i] * 150 for i in range(3)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Cost:", m.getObjVal())
