"""広告予算メディアミックス配分 (Media Mix Advertising)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Media_Mix")
    # TV, Web, 新聞の予算
    x = {i: model.addVar(vtype="C", lb=0, name=f"x_{i}") for i in range(3)}
    model.addCons(quicksum(x[i] for i in range(3)) <= 10000, "budget_limit")
    # 各メディアの露出数（収穫逓減の区分線形化の簡易版）
    model.setObjective(5 * x[0] + 8 * x[1] + 3 * x[2], "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Exposures:", m.getObjVal())
