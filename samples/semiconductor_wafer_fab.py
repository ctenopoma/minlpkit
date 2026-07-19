"""半導体ウェハ工場搬送スケジュール (Semiconductor Wafer Fab Routing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Semiconductor_Wafer_Fab")
    # 搬送ロボットの割り当て
    assign = {(w, r): model.addVar(vtype="B", name=f"as_{w}_{r}") for w in range(2) for r in range(2)}
    for w in range(2):
        model.addCons(quicksum(assign[w, r] for r in range(2)) == 1, f"wafer_{w}")
    model.setObjective(quicksum(assign[w, r] * (5 + r * 2) for w in range(2) for r in range(2)), "minimize")
    model.data = {"assign": assign}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Routing Time:", m.getObjVal())
