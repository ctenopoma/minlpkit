"""自動車塗装順序最適化 (Automotive Paint Shop Sequencing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Automotive_Paint_Shop")
    # 色変更ペナルティの最小化
    change = {i: model.addVar(vtype="B", name=f"ch_{i}") for i in range(3)}
    model.addCons(quicksum(change[i] for i in range(3)) >= 1, "min_changes")
    model.setObjective(quicksum(change[i] * 50 for i in range(3)), "minimize")
    model.data = {"change": change}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Change Cost:", m.getObjVal())
