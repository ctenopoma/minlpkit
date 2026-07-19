"""多品種サプライチェーン計画 (Multi-commodity Supply Chain Planning)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("SupplyChain_MultiCommodity")
    COMMODITIES = ["A", "B"]
    x = {c: model.addVar(vtype="C", lb=0, name=f"x_{c}") for c in COMMODITIES}
    model.addCons(quicksum(x[c] for c in COMMODITIES) <= 100, "capacity")
    model.addCons(x["A"] >= 30, "demand_A")
    model.addCons(x["B"] >= 40, "demand_B")
    model.setObjective(5 * x["A"] + 8 * x["B"], "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
