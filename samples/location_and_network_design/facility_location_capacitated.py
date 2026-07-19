"""容量制約付き施設配置問題 (Capacitated Facility Location)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Capacitated_Facility_Location")
    FACILITIES = ["F1", "F2"]; CUSTOMERS = ["C1", "C2", "C3"]
    CAP = {"F1": 100, "F2": 80}
    DEMAND = {"C1": 30, "C2": 40, "C3": 50}
    y = {f: model.addVar(vtype="B", name=f"y_{f}") for f in FACILITIES}
    x = {(f, c): model.addVar(vtype="C", lb=0, name=f"x_{f}_{c}") for f in FACILITIES for c in CUSTOMERS}
    for c in CUSTOMERS:
        model.addCons(quicksum(x[f, c] for f in FACILITIES) >= DEMAND[c], f"demand_{c}")
    for f in FACILITIES:
        model.addCons(quicksum(x[f, c] for c in CUSTOMERS) <= CAP[f] * y[f], f"cap_{f}")
    model.setObjective(quicksum(1000 * y[f] for f in FACILITIES) + quicksum(2 * x[f, c] for f in FACILITIES for c in CUSTOMERS), "minimize")
    model.data = {"x": x, "y": y}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
