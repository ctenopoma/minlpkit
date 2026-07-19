"""地域冷暖房配管網熱供給計画 (District Heating Grid)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("District_Heating_Grid")
    # 簡易パイプライン熱損失
    heat_in = model.addVar(vtype="C", lb=0, name="heat_in")
    heat_loss = model.addVar(vtype="C", lb=0, name="heat_loss")
    model.addCons(heat_loss == 0.05 * heat_in, "loss_equation")
    model.addCons(heat_in - heat_loss >= 100, "demand")
    model.setObjective(1.2 * heat_in, "minimize")
    model.data = {"heat_in": heat_in}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
