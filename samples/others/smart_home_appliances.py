"""スマートホーム家電個別制御スケジュール (Smart Home Appliances)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Smart_Home_Appliances")
    T = 6
    x = {t: model.addVar(vtype="B", name=f"x_{t}") for t in range(T)}
    # 家電は期間内に2時間だけ動作
    model.addCons(quicksum(x[t] for t in range(T)) == 2, "run_time")
    # 電気代単価
    PRICES = [10, 12, 18, 20, 12, 8]
    model.setObjective(quicksum(x[t] * PRICES[t] for t in range(T)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
