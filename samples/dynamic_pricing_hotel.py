"""ホテル部屋割・動的価格決定 (Dynamic Pricing for Hotel Rooms)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Dynamic_Pricing_Hotel")
    # 部屋価格 P, 需要 D = a - b * P, 売上 R = P * D (非線形)
    p = model.addVar(vtype="C", lb=80, ub=200, name="p")
    d = model.addVar(vtype="C", lb=0, ub=50, name="d")
    r = model.addVar(vtype="C", lb=0, name="r")
    model.addCons(d == 60 - 0.25 * p, "demand_curve")
    model.addCons(r == p * d, "revenue_definition")
    model.setObjective(r, "maximize")
    model.data = {"p": p, "r": r}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Optimal Price:", m.getVal(m.data["p"]))
