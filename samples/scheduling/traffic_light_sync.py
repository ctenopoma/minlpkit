"""信号制御同期化・渋滞緩和 (Traffic Light Synchronization)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Traffic_Light_Sync")
    # 信号の青時間 [秒]
    green = {i: model.addVar(vtype="C", lb=15, ub=60, name=f"green_{i}") for i in range(2)}
    model.addCons(green[0] + green[1] <= 90, "cycle_limit")
    model.setObjective(quicksum(green[i] * 1.5 for i in range(2)), "maximize")
    model.data = {"green": green}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Green Time:", m.getObjVal())
