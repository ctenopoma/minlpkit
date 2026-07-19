"""航空便オーバーブッキング・収益管理 (Airline Overbooking Control)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Airline_Overbooking")
    # 予約受付数 (オーバーブッキング許容)
    bk = model.addVar(vtype="I", lb=100, ub=120, name="bk")
    # キャンセルコストとチケット販売額
    model.setObjective(150 * bk - 300 * (bk - 100), "maximize")
    model.data = {"bk": bk}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())
