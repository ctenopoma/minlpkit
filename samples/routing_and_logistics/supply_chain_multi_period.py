"""多期間サプライチェーンネットワーク計画 (Multi-period Supply Chain Network Planning)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("SupplyChain_MultiPeriod")
    T = 4; NODES = ["Plant", "DC", "Customer"]
    # 決定変数: 輸送量, 在庫量
    x = {t: model.addVar(vtype="C", lb=0, name=f"x_{t}") for t in range(T)}
    s = {t: model.addVar(vtype="C", lb=0, name=f"s_{t}") for t in range(T)}
    # 在庫バランス
    for t in range(T):
        if t == 0:
            model.addCons(x[t] - s[t] == 20, name=f"bal_{t}")
        else:
            model.addCons(s[t-1] + x[t] - s[t] == 20 + t * 5, name=f"bal_{t}")
    model.setObjective(quicksum(10 * x[t] + 2 * s[t] for t in range(T)), "minimize")
    model.data = {"x": x, "s": s}
    return model
if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Cost:", m.getObjVal())
