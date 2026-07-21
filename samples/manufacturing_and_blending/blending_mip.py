"""配合設計問題(整数変数付き) (Blending Problem, MIP variant)

事業ストーリー
--------------
飼料工場の配合(フォーミュレーション)担当者が、トウモロコシ・大豆粕・魚粉などの
原材料を混ぜ合わせ、規定のタンパク質含有率・脂肪含有率を満たす配合飼料をロット
生産する。各原材料は仕入先との取引条件により「使うなら最低ロット量以上」という
最小購入量の縛りがあり、少量だけつまみ食い的に使うことはできない。栄養基準を
満たしつつ、原材料費の合計を最小化する配合レシピを決める必要がある。

各制約の業務的意味:
- **総生産量の充足**: 使用する原材料の合計量が、生産すべき製品量とちょうど一致
  しなければならない。
- **タンパク質含有率の下限**: 完成品全体のタンパク質量が、栄養基準で定められた
  最低量を下回ってはならない(飼料としての栄養価を保証する)。
- **脂肪含有率の上限**: 完成品全体の脂肪量が、規格上限を超えてはならない
  (過剰な脂肪分は保存性・品質に悪影響を与える)。
- **最小購入量とオン/オフの連動**: ある原材料を「使う」と決めたら、仕入先との
  取引条件上の最低ロット量以上を購入しなければならない。使わないなら使用量は
  ゼロにする(二値変数で購入量の上下限を切り替える)。

(元の学術的定義: Dantzig (1955) - The Diet Problem, extended with integer constraints.)
"""

from pyscipopt import Model

def build_model(infeasible=False):
    model = Model("BlendingMIP")

    # 飼料原材料8種(コスト・タンパク質率・脂肪率は実際の配合飼料表を参考にした概算値)
    materials = ["Corn", "Soymeal", "Fishmeal", "Wheat",
                 "CanolaMeal", "Barley", "Molasses", "MineralMix"]
    costs = {"Corn": 18, "Soymeal": 32, "Fishmeal": 55, "Wheat": 20,
             "CanolaMeal": 28, "Barley": 17, "Molasses": 22, "MineralMix": 40}
    protein = {"Corn": 0.09, "Soymeal": 0.44, "Fishmeal": 0.60, "Wheat": 0.12,
               "CanolaMeal": 0.36, "Barley": 0.10, "Molasses": 0.04, "MineralMix": 0.00}
    fat = {"Corn": 0.04, "Soymeal": 0.02, "Fishmeal": 0.10, "Wheat": 0.02,
           "CanolaMeal": 0.04, "Barley": 0.02, "Molasses": 0.01, "MineralMix": 0.00}

    req_product = 500
    min_protein = 0.16 * req_product
    max_fat = 0.06 * req_product
    min_purchase = 25

    # Variables
    x = {} # Amount of material
    y = {} # 1 if material is used
    for m in materials:
        x[m] = model.addVar(vtype="C", lb=0, name=f"amt_{m}")
        y[m] = model.addVar(vtype="B", name=f"use_{m}")

    # Constraints
    # Total product
    model.addCons(sum(x[m] for m in materials) == req_product, name="total_product")

    # Nutrition
    model.addCons(sum(protein[m] * x[m] for m in materials) >= min_protein, name="min_protein")
    model.addCons(sum(fat[m] * x[m] for m in materials) <= max_fat, name="max_fat")

    # Logical constraints and min purchase
    bigM = 1000
    for m in materials:
        model.addCons(x[m] <= bigM * y[m], name=f"logic_upper_{m}")
        model.addCons(x[m] >= min_purchase * y[m], name=f"logic_lower_{m}")

    if infeasible:
        model.addCons(sum(x[m] for m in materials) == req_product + 10, name="inf_constraint")

    # Objective
    model.setObjective(sum(costs[m] * x[m] for m in materials), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
