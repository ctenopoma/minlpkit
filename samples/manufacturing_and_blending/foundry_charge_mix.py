"""鋳造配合設計（原料ブレンド） (Foundry Charge Mix)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Foundry_Charge_Mix")
    # 鉄・炭素の配合比率
    scrap = model.addVar(vtype="C", lb=0, name="scrap")
    pigiron = model.addVar(vtype="C", lb=0, name="pigiron")
    model.addCons(scrap + pigiron == 10.0, "total_weight")
    # 炭素濃度制限 (scrap: 2%, pigiron: 4% -> 合計で 3.2% 以上)
    model.addCons(0.02 * scrap + 0.04 * pigiron >= 0.032 * 10.0, "carbon_content")
    model.setObjective(200 * scrap + 350 * pigiron, "minimize")
    model.data = {"scrap": scrap, "pigiron": pigiron}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Material Cost:", m.getObjVal())
