"""ガラス2次元切り出しパターン生成 (Glass Cutting 2D)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Glass_Cutting_2D")
    # 2次元ギロチンカット制限
    x = model.addVar(vtype="C", lb=0, ub=100, name="x")
    y = model.addVar(vtype="C", lb=0, ub=80, name="y")
    # 面積 (非線形)
    area = model.addVar(vtype="C", lb=0, name="area")
    model.addCons(area == x * y, "area_eq")
    model.addCons(area >= 2000, "min_area")
    model.setObjective(x + y, "minimize")
    model.data = {"x": x, "y": y}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Perimeter:", m.getObjVal())
