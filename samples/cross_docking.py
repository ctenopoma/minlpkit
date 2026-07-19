"""クロスドッキングスケジュール最適化 (Cross-docking Scheduling)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Cross_Docking")
    # トラック到着・出発時間
    t_in = {i: model.addVar(vtype="C", lb=0, name=f"t_in_{i}") for i in range(2)}
    t_out = {j: model.addVar(vtype="C", lb=0, name=f"t_out_{j}") for j in range(2)}
    model.addCons(t_out[0] >= t_in[0] + 2, "unload_0")
    model.addCons(t_out[1] >= t_in[1] + 3, "unload_1")
    model.setObjective(quicksum(t_out[j] for j in range(2)), "minimize")
    model.data = {"t_in": t_in, "t_out": t_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Makespan:", m.getObjVal())
