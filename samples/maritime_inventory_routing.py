"""海運在庫配送計画問題 (Maritime Inventory Routing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Maritime_Inventory_Routing")
    T = 5
    # ポートの在庫
    inv = {t: model.addVar(vtype="C", lb=10, ub=100, name=f"inv_{t}") for t in range(T)}
    # 荷役量
    q = {t: model.addVar(vtype="C", lb=0, name=f"q_{t}") for t in range(T)}
    for t in range(T):
        if t == 0:
            model.addCons(inv[t] == 50 - 15 + q[t])
        else:
            model.addCons(inv[t] == inv[t-1] - 15 + q[t])
    model.setObjective(quicksum(q[t] * 20 for t in range(T)), "minimize")
    model.data = {"inv": inv, "q": q}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
