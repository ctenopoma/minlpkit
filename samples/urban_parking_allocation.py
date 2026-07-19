"""都市型スマート駐車場予約割当 (Urban Parking Allocation)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Urban_Parking")
    # 車両を駐車スペースに割り当て
    x = {(c, s): model.addVar(vtype="B", name=f"x_{c}_{s}") for c in range(2) for s in range(2)}
    for c in range(2):
        model.addCons(quicksum(x[c, s] for s in range(2)) == 1)
    model.setObjective(quicksum(x[c, s] * (15 - s*2) for c in range(2) for s in range(2)), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Utility:", m.getObjVal())
