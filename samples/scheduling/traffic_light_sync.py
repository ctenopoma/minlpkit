"""信号制御同期化・渋滞緩和 (Traffic Light Synchronization)

自治体の交通管制センターが、幹線道路沿いに並ぶ複数交差点の信号サイクルにおける
青時間配分とオフセット(隣接交差点との信号切替タイミング差)を同時に決める意思決定である。
各交差点はサイクル長(赤+青時間の合計)を守りつつ需要方向に十分な青時間を割り当てる必要が
あり、さらに隣接交差点間のオフセットが車両の平均走行速度で決まる走行時間から大きく外れると
「グリーンウェーブ」(連続して青信号を通過できる状態)が崩れて停止回数が増える。
オフセットの適否は0-1の整数判断(狙いの走行時間帯に収まっているか)で表現し、
青時間配分の連続決定と組み合わせて交差点網全体の待ち時間を最小化する。
"""

from pyscipopt import Model, quicksum

INTERSECTIONS = range(4)
CYCLE = 90.0  # 信号サイクル長[秒](共通)
MIN_GREEN, MAX_GREEN = 15.0, 60.0
demand_flow = {0: 1.2, 1: 1.5, 2: 1.0, 3: 1.3}  # 交差点ごとの需要重み(青時間の値の高さ)
link_distance = {(0, 1): 300.0, (1, 2): 250.0, (2, 3): 350.0}  # 区間距離[m]
avg_speed = 10.0  # 想定走行速度[m/s]
BIG_M = CYCLE


def build_model():
    model = Model("Traffic_Light_Sync")

    green = {i: model.addVar(vtype="C", lb=MIN_GREEN, ub=MAX_GREEN, name=f"green_{i}") for i in INTERSECTIONS}
    offset = {i: model.addVar(vtype="C", lb=0, ub=CYCLE, name=f"offset_{i}") for i in INTERSECTIONS}
    # 区間ごとに「グリーンウェーブが成立しているか」を表す0-1変数
    wave_ok = {link: model.addVar(vtype="B", name=f"wave_{link}") for link in link_distance}

    for i in INTERSECTIONS:
        model.addCons(green[i] <= CYCLE, name=f"cycle_limit_{i}")

    for (i, j), dist in link_distance.items():
        travel_time = dist / avg_speed
        diff = offset[j] - offset[i] - travel_time
        # wave_ok=1のときのみオフセット差が走行時間の±5秒以内に収まることを要求(big-M)
        model.addCons(diff <= 5.0 + BIG_M * (1 - wave_ok[i, j]), name=f"wave_upper_{i}_{j}")
        model.addCons(diff >= -5.0 - BIG_M * (1 - wave_ok[i, j]), name=f"wave_lower_{i}_{j}")

    model.setObjective(
        quicksum(demand_flow[i] * green[i] for i in INTERSECTIONS)
        + quicksum(40.0 * wave_ok[link] for link in link_distance),
        "maximize",
    )
    model.data = {"green": green, "offset": offset, "wave_ok": wave_ok}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Total Green Time Value:", m.getObjVal())
