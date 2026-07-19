"""小売シーズン値引き価格最適化 (Price Optimization with Markdown)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Markdown_Price_Optimization")
    # 価格 P, 需要 D = a - b*P (非線形/双線形売上 P*D)
    price = model.addVar(vtype="C", lb=10, ub=50, name="price")
    demand = model.addVar(vtype="C", lb=0, name="demand")
    revenue = model.addVar(vtype="C", lb=0, name="revenue")
    model.addCons(demand == 100 - 2 * price, "demand_curve")
    model.addCons(revenue == price * demand, "revenue_definition")
    model.setObjective(revenue, "maximize")
    model.data = {"price": price, "revenue": revenue}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Revenue:", m.getObjVal())
