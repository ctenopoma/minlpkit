"""仮想発電所 (VPP) 入札・制御最適化 (Virtual Power Plant Control)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Virtual_Power_Plant")
    T = 4
    # 各DERの出力
    der1 = {t: model.addVar(vtype="C", lb=0, ub=20, name=f"der1_{t}") for t in range(T)}
    der2 = {t: model.addVar(vtype="C", lb=0, ub=30, name=f"der2_{t}") for t in range(T)}
    bid = {t: model.addVar(vtype="C", lb=0, name=f"bid_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(bid[t] == der1[t] + der2[t], f"aggregation_{t}")
    model.setObjective(quicksum(bid[t] * 15 for t in range(T)), "maximize")
    model.data = {"bid": bid}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Revenue:", m.getObjVal())
