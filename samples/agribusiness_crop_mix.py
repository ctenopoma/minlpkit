"""農業作物ミックス計画 (Agribusiness Crop Mix Planning)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Agribusiness_Crop_Mix")
    # 各作物の作付面積 (ha)
    wheat = model.addVar(vtype="C", lb=0, name="wheat")
    corn = model.addVar(vtype="C", lb=0, name="corn")
    model.addCons(wheat + corn <= 500, "total_land")
    model.addCons(1.5 * wheat + 2.0 * corn <= 800, "water_limit")
    model.setObjective(400 * wheat + 600 * corn, "maximize")
    model.data = {"wheat": wheat, "corn": corn}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Profit:", m.getObjVal())
