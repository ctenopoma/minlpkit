"""時間枠付き配送計画問題 (Vehicle Routing with Time Windows)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("VRP_Time_Windows")
    # 簡易時間枠定式化
    t = {i: model.addVar(vtype="C", lb=0, name=f"t_{i}") for i in range(3)}
    model.addCons(t[1] >= t[0] + 5, "travel_0_1")
    model.addCons(t[2] >= t[1] + 4, "travel_1_2")
    # 時間枠制約
    model.addCons(t[1] <= 15, "tw_upper_1")
    model.addCons(t[2] <= 25, "tw_upper_2")
    model.setObjective(t[2], "minimize")
    model.data = {"t": t}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total time:", m.getObjVal())
