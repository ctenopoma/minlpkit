"""ハブ＆スポークネットワーク設計 (Hub and Spoke Network Design)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Hub_And_Spoke")
    NODES = ["N1", "N2", "N3"]
    # ハブの開設変数
    h = {i: model.addVar(vtype="B", name=f"h_{i}") for i in NODES}
    model.addCons(quicksum(h[i] for i in NODES) == 1, "exactly_one_hub")
    model.setObjective(quicksum(500 * h[i] for i in NODES), "minimize")
    model.data = {"h": h}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
