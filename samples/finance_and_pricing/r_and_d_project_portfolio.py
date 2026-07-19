"""R&D新規事業投資ポートフォリオ (R&D Project Portfolio)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("RD_Project_Portfolio")
    # プロジェクト採択有無
    select = {i: model.addVar(vtype="B", name=f"select_{i}") for i in range(4)}
    COSTS = [100, 250, 180, 300]
    RETURNS = [150, 400, 240, 500]
    model.addCons(quicksum(select[i] * COSTS[i] for i in range(4)) <= 500, "budget")
    model.setObjective(quicksum(select[i] * RETURNS[i] for i in range(4)), "maximize")
    model.data = {"select": select}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Return:", m.getObjVal())
