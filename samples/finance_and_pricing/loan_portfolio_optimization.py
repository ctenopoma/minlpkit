"""ローン与信ポートフォリオ利回り最大化 (Loan Portfolio Optimization)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Loan_Portfolio")
    # 融資タイプ別割当
    w = {i: model.addVar(vtype="C", lb=0, name=f"w_{i}") for i in range(3)}
    model.addCons(quicksum(w[i] for i in range(3)) == 1000.0, "total_loan")
    # 不良債権比率（デフォルト確率）の加重平均上限
    model.addCons(0.01 * w[0] + 0.03 * w[1] + 0.05 * w[2] <= 0.03 * 1000.0, "risk_limit")
    model.setObjective(quicksum(w[i] * (0.04 + i * 0.01) for i in range(3)), "maximize")
    model.data = {"w": w}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Yield:", m.getObjVal())
