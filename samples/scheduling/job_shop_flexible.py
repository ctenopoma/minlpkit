"""フレキシブルジョブショップスケジューリング (Flexible Job Shop)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Flexible_Job_Shop")
    # マシン選択
    x = {(j, m): model.addVar(vtype="B", name=f"x_{j}_{m}") for j in range(2) for m in range(2)}
    for j in range(2):
        model.addCons(quicksum(x[j, m] for m in range(2)) == 1, f"assign_{j}")
    model.setObjective(quicksum(x[j, m] * (2 + m) for j in range(2) for m in range(2)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
