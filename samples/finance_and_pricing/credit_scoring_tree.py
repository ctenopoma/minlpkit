"""信用リスク評価の閾値分類 (Credit Scoring Tree)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Credit_Scoring_Tree")
    threshold = model.addVar(vtype="C", lb=300, ub=850, name="threshold")
    # 分類誤差ペナルティの最小化 (簡易定式化)
    model.addCons(threshold >= 550, "default_safety_margin")
    model.setObjective(threshold, "minimize")
    model.data = {"threshold": threshold}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Threshold:", m.getObjVal())
