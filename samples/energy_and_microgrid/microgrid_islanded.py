"""孤立型マイクログリッド運転計画 (Islanded Microgrid)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Islanded_Microgrid")
    T = 3
    gen = {t: model.addVar(vtype="C", lb=10, ub=50, name=f"gen_{t}") for t in range(T)}
    shed = {t: model.addVar(vtype="C", lb=0, name=f"shed_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(gen[t] + shed[t] == 60, f"balance_{t}")
    model.setObjective(quicksum(5 * gen[t] + 100 * shed[t] for t in range(T)), "minimize")
    model.data = {"gen": gen, "shed": shed}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
