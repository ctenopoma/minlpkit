"""水火力電源協調運転計画 (Hydro-Thermal Coordination)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Hydro_Thermal_Coordination")
    T = 3
    p_hydro = {t: model.addVar(vtype="C", lb=0, ub=50, name=f"ph_{t}") for t in range(T)}
    p_thermal = {t: model.addVar(vtype="C", lb=0, ub=100, name=f"pt_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(p_hydro[t] + p_thermal[t] >= 80, f"demand_{t}")
    # 水力発電の総電力量制限 (水資源制限)
    model.addCons(quicksum(p_hydro[t] for t in range(T)) <= 70, "water_limit")
    model.setObjective(quicksum(20 * p_thermal[t] + 2 * p_hydro[t] for t in range(T)), "minimize")
    model.data = {"p_hydro": p_hydro, "p_thermal": p_thermal}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
