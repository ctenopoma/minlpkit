"""空港フライト・ゲート自動割当 (Airport Gate Assignment)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Airport_Gate_Assignment")
    FLIGHTS = ["F1", "F2"]; GATES = ["G1", "G2"]
    x = {(f, g): model.addVar(vtype="B", name=f"x_{f}_{g}") for f in FLIGHTS for g in GATES}
    for f in FLIGHTS:
        model.addCons(quicksum(x[f, g] for g in GATES) == 1)
    for g in GATES:
        model.addCons(quicksum(x[f, g] for f in FLIGHTS) <= 1)
    model.setObjective(quicksum(x[f, g] * 100 for f in FLIGHTS for g in GATES), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Satisfaction Value:", m.getObjVal())
