"""バス運転士勤務表自動生成 (Bus Driver Rostering)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Bus_Driver_Rostering")
    # 運転士シフト割当 (2人, 3スロット)
    x = {(d, s): model.addVar(vtype="B", name=f"x_{d}_{s}") for d in range(2) for s in range(3)}
    for s in range(3):
        model.addCons(quicksum(x[d, s] for d in range(2)) == 1, f"slot_{s}")
    for d in range(2):
        model.addCons(quicksum(x[d, s] for s in range(3)) <= 2, f"max_work_{d}")
    model.setObjective(quicksum(x[d, s] * 100 for d in range(2) for s in range(3)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
