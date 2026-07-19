"""送電線拡張計画 (Transmission Expansion Planning)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Transmission_Expansion")
    LINES = ["L1", "L2"]
    build = {l: model.addVar(vtype="B", name=f"build_{l}") for l in LINES}
    flow = {l: model.addVar(vtype="C", lb=0, ub=50, name=f"flow_{l}") for l in LINES}
    for l in LINES:
        model.addCons(flow[l] <= 100 * build[l], f"capacity_{l}")
    model.addCons(quicksum(flow[l] for l in LINES) >= 60, "demand")
    model.setObjective(quicksum(1000 * build[l] + 2 * flow[l] for l in LINES), "minimize")
    model.data = {"build": build, "flow": flow}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
