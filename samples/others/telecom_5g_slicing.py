"""5Gネットワークスライシングリソース割当 (5G Telecom Slicing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Telecom_5G_Slicing")
    # スライス帯域割当
    slice_bw = {i: model.addVar(vtype="C", lb=5, name=f"slice_bw_{i}") for i in range(3)}
    model.addCons(quicksum(slice_bw[i] for i in range(3)) <= 100, "total_bandwidth")
    model.setObjective(quicksum(slice_bw[i] * 12 for i in range(3)), "maximize")
    model.data = {"slice_bw": slice_bw}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())
