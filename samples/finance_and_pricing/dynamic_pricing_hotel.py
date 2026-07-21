"""ホテル客室の動的価格決定 (Dynamic Pricing for Hotel Rooms)

事業ストーリー
--------------
ホテルのレベニューマネージャーが、複数の部屋タイプ(スタンダード・スイート等)について
曜日区分(平日・週末・繁忙日)ごとの販売価格を決める。価格を上げれば単価は上がるが
価格弾力的な需要曲線に沿って予約数は減るため、収益(価格×需要)は価格の非線形(二次)関数になる。
客室在庫という物理的な容量制約に加え、週末・繁忙日は平日より高い価格設定にするという
レベニューマネジメントの業務ルール(価格の順序制約)を反映する。
"""

from pyscipopt import Model, quicksum

ROOM_TYPES = ["standard", "suite"]
PERIODS = ["weekday", "weekend", "peak"]

# 需要曲線パラメータ: d = a - b * p (部屋タイプ・期間別)
A = {("standard", "weekday"): 55, ("standard", "weekend"): 65, ("standard", "peak"): 70,
     ("suite", "weekday"): 25, ("suite", "weekend"): 32, ("suite", "peak"): 38}
B = {"standard": 0.28, "suite": 0.12}
CAPACITY = {"standard": 40, "suite": 15}          # 客室在庫[室/夜]
PRICE_BOUNDS = {"standard": (70, 220), "suite": (150, 450)}


def build_model():
    model = Model("Dynamic_Pricing_Hotel")
    R, P = ROOM_TYPES, PERIODS

    p = {(r, t): model.addVar(vtype="C", lb=PRICE_BOUNDS[r][0], ub=PRICE_BOUNDS[r][1],
                              name=f"p_{r}_{t}") for r in R for t in P}
    d = {(r, t): model.addVar(vtype="C", lb=0, ub=CAPACITY[r], name=f"d_{r}_{t}") for r in R for t in P}
    rev = {(r, t): model.addVar(vtype="C", lb=0, name=f"rev_{r}_{t}") for r in R for t in P}

    for r in R:
        for t in P:
            model.addCons(d[r, t] == A[r, t] - B[r] * p[r, t], f"demand_curve_{r}_{t}")
            model.addCons(d[r, t] <= CAPACITY[r], f"capacity_{r}_{t}")
            # 収益 = 価格 × 需要(双線形)
            model.addCons(rev[r, t] == p[r, t] * d[r, t], f"revenue_def_{r}_{t}")

    # レベニューマネジメント業務ルール: 週末・繁忙日は平日より高値設定
    for r in R:
        model.addCons(p[r, "weekend"] >= 1.1 * p[r, "weekday"], f"order_weekend_{r}")
        model.addCons(p[r, "peak"] >= 1.2 * p[r, "weekday"], f"order_peak_{r}")

    model.setObjective(quicksum(rev[r, t] for r in R for t in P), "maximize")

    model.data = {"p": p, "d": d, "rev": rev}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Revenue:", m.getObjVal())
