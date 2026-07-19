"""シェアサイクル再配置ルート (Bike Sharing Rebalancing)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Bike_Rebalancing")
    # 移動させる自転車数
    move = {(i, j): model.addVar(vtype="I", lb=0, name=f"move_{i}_{j}") for i in range(2) for j in range(2) if i != j}
    model.addCons(move[0, 1] >= 5, "demand_station_1")
    model.setObjective(move[0, 1] * 8, "minimize")
    model.data = {"move": move}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Rebalance Cost:", m.getObjVal())
