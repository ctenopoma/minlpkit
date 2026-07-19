"""配車サービス・ドライバーマッチング (Ride-hailing Matching)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Ride_Hailing_Matching")
    # ドライバーと乗客のマッチング
    match = {(d, p): model.addVar(vtype="B", name=f"m_{d}_{p}") for d in range(2) for p in range(2)}
    for d in range(2):
        model.addCons(quicksum(match[d, p] for p in range(2)) <= 1)
    for p in range(2):
        model.addCons(quicksum(match[d, p] for d in range(2)) <= 1)
    model.setObjective(quicksum(match[d, p] * (20 - d*2) for d in range(2) for p in range(2)), "maximize")
    model.data = {"match": match}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Match Value:", m.getObjVal())
