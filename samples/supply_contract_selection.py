"""調達契約オプション選定 (Supply Contract Selection)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Supply_Contract_Selection")
    # 契約オプション (A, B)
    opt = {i: model.addVar(vtype="B", name=f"opt_{i}") for i in range(2)}
    model.addCons(quicksum(opt[i] for i in range(2)) == 1, "exactly_one_contract")
    model.setObjective(120 * opt[0] + 150 * opt[1], "minimize")
    model.data = {"opt": opt}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Contract Cost:", m.getObjVal())
