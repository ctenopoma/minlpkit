"""EV都市充電スタンド配置最適化 (EV Charging Network Design)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("EV_Charging_Network")
    LOCS = ["Loc1", "Loc2"]
    open_st = {l: model.addVar(vtype="B", name=f"open_{l}") for l in LOCS}
    model.addCons(quicksum(open_st[l] for l in LOCS) >= 1, "at_least_one")
    model.setObjective(quicksum(open_st[l] * 50000 for l in LOCS), "minimize")
    model.data = {"open_st": open_st}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Cost:", m.getObjVal())
