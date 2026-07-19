"""飲料ボトリング段取り最適化 (Beverage Bottling Line Scheduling)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Beverage_Bottling_Line")
    # 製品の切り替え順序
    switch = {(i, j): model.addVar(vtype="B", name=f"sw_{i}_{j}") for i in range(3) for j in range(3) if i != j}
    model.addCons(quicksum(switch[0, j] for j in [1, 2]) == 1)
    model.setObjective(quicksum(switch[i, j] * 30 for i in range(3) for j in range(3) if i != j), "minimize")
    model.data = {"switch": switch}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Time:", m.getObjVal())
