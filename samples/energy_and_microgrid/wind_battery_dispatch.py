"""風力発電と蓄電池の協調制御 (Wind and Battery Dispatch)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Wind_Battery_Dispatch")
    T = 4
    WIND = [10, 20, 15, 5]
    p_out = {t: model.addVar(vtype="C", lb=0, name=f"p_out_{t}") for t in range(T)}
    p_chg = {t: model.addVar(vtype="C", lb=0, ub=10, name=f"chg_{t}") for t in range(T)}
    p_dis = {t: model.addVar(vtype="C", lb=0, ub=10, name=f"dis_{t}") for t in range(T)}
    soc = {t: model.addVar(vtype="C", lb=0, ub=30, name=f"soc_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(p_out[t] == WIND[t] - p_chg[t] + p_dis[t], f"balance_{t}")
        if t == 0:
            model.addCons(soc[t] == 15 + p_chg[t] - p_dis[t])
        else:
            model.addCons(soc[t] == soc[t-1] + p_chg[t] - p_dis[t])
    model.setObjective(quicksum(p_out[t] * 15 for t in range(T)), "maximize")
    model.data = {"p_out": p_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())
