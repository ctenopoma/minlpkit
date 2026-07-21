"""配車サービス・ドライバーマッチング (Ride-hailing Matching)

事業ストーリー
--------------
配車プラットフォームの「ディスパッチ担当」(自動マッチングエンジン)が、ある短い時間窓に
発生した複数の配車リクエストに対して、稼働中の複数ドライバーをどう割り当てるかを決める
意思決定である。各ドライバーは同時に1件までしか対応できず、各乗客も1台のみに割り当てら
れる(一対一マッチング)。マッチングの価値はドライバーと乗客の距離(迎車時間)・乗客の
優先度(プレミアム会員か)によって変わる。さらに一部ドライバーは長距離配車を避けたい
という上限(1シフトあたりの走行距離上限)を持つため、複数リクエストへの累積割当量にも
制約がかかる。ディスパッチ担当は、これらの制約下でマッチング価値の合計を最大化する
割当を決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_driver=4, n_passenger=4),
    "default": dict(n_driver=6, n_passenger=6),
    "large": dict(n_driver=8, n_passenger=8),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_driver, n_passenger = cfg["n_driver"], cfg["n_passenger"]
    drivers, passengers = range(n_driver), range(n_passenger)

    # マッチング価値: 距離(迎車時間)が近いほど高、プレミアム乗客はボーナス
    distance = {(d, p): 3 + (d * 7 + p * 5) % 15 for d in drivers for p in passengers}
    is_premium = {p: 1 if p % 3 == 0 else 0 for p in passengers}
    value = {(d, p): max(5, 30 - distance[d, p]) + 8 * is_premium[p] for d in drivers for p in passengers}
    trip_distance = {(d, p): distance[d, p] for d in drivers for p in passengers}

    max_shift_distance = 45  # ドライバー1人あたりのシフト内走行距離上限

    model = Model("Ride_Hailing_Matching")

    match = {(d, p): model.addVar(vtype="B", name=f"m_{d}_{p}") for d in drivers for p in passengers}

    for d in drivers:
        model.addCons(quicksum(match[d, p] for p in passengers) <= 1, name=f"driver_cap_{d}")
        model.addCons(
            quicksum(match[d, p] * trip_distance[d, p] for p in passengers) <= max_shift_distance,
            name=f"shift_distance_{d}")
    for p in passengers:
        model.addCons(quicksum(match[d, p] for d in drivers) <= 1, name=f"passenger_cap_{p}")

    model.setObjective(quicksum(match[d, p] * value[d, p] for d in drivers for p in passengers), "maximize")
    model.data = {"match": match, "dims": (n_driver, n_passenger)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Match Value:", m.getObjVal())
