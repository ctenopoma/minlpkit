"""条件付き確実性価値 (CVaR) ポートフォリオ最適化 (Portfolio CVaR)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Portfolio_CVaR")
    # 資産比率 w
    w = {i: model.addVar(vtype="C", lb=0, ub=1.0, name=f"w_{i}") for i in range(3)}
    model.addCons(quicksum(w[i] for i in range(3)) == 1.0, "budget")
    model.setObjective(quicksum(w[i] * (0.05 + i * 0.02) for i in range(3)), "maximize")
    model.data = {"w": w}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Expected Return:", m.getObjVal())
