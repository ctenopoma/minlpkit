"""鉄道運行系統・線路容量計画 (Railway Line Planning)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Railway_Line_Planning")
    # 運行頻度
    freq = {i: model.addVar(vtype="I", lb=1, ub=10, name=f"freq_{i}") for i in range(2)}
    model.addCons(quicksum(freq[i] for i in range(2)) <= 15, "line_capacity")
    model.setObjective(quicksum(freq[i] * 500 for i in range(2)), "maximize")
    model.data = {"freq": freq}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())
