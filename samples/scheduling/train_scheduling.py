"""電車運行計画・列車ダイヤグラム最適化問題 (Train Timetable Scheduling)

同一の鉄道路線（複数駅）を走行する複数の列車（急行列車と普通列車など）のダイヤグラム（運行時間表）を最適化します。
駅間走行時間、駅での最低停車時間、および同一線路上での衝突を回避するための安全車間時間（ヘッドウェイ）を考慮します。
急行列車が普通列車を追い越す際の退避駅での待避関係を決定するため、
列車間の先行・後続順序を表すバイナリ変数を用いた混合整数線形計画法 (MILP) モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Train_Timetable_Scheduling")

    # ---- データ設定 ----
    # 駅 (Station 0: 始発駅, Station 3: 終着駅)
    STATIONS = [0, 1, 2, 3]  # 4つの駅
    
    # 列車: 急行 (Express) と 普通 (Local)
    TRAINS = ["Local_1", "Express_2", "Local_3"]
    
    # 各列車の始発駅出発時刻の最小下限 (スケジュール開始のタイミング)
    RELEASE_TIMES = {
        "Local_1": 0.0,    # 0分に出発可能
        "Express_2": 10.0, # 10分に出発可能 (後ろから急行が追いかける)
        "Local_3": 15.0,   # 15分に出発可能
    }

    # 駅間最小走行時間 [分]
    # RUN_TIME[train_type, from_station]
    # 急行は普通よりも早く走れる
    RUN_TIMES = {
        ("Local", 0): 8.0,  # 駅0 -> 駅1
        ("Local", 1): 8.0,  # 駅1 -> 駅2
        ("Local", 2): 8.0,  # 駅2 -> 駅3
        ("Express", 0): 5.0,
        ("Express", 1): 5.0,
        ("Express", 2): 5.0,
    }

    # 最小停車時間 [分] (始発・終着は除く、中間駅1, 2のみ)
    MIN_STOP = 1.0

    # 安全車間時間 (ヘッドウェイ) [分]
    # 同一駅からの出発間隔および同一駅への到着間隔は、最低 3 分空ける必要がある
    HEADWAY = 3.0

    # 退避可能な駅のフラグ (追い越しは中間駅1, 2でのみ可能)
    # 普通列車が中間駅に停車している間に、急行列車が追い越すことができる
    # 単線または追い越し設備がない区間での追い越しを防ぐため、駅間での順序は保存される
    # (例: 区間 s->s+1 の順序は、駅s出発時の順序と一致する)

    BIG_M = 1000.0

    # ---- 変数定義 ----
    # a[i, s]: 列車 i が駅 s に到着する時刻 (連続)
    a = {}
    # d[i, s]: 列車 i が駅 s を出発する時刻 (連続)
    for i in TRAINS:
        for s in STATIONS:
            a[i, s] = model.addVar(vtype="C", lb=0.0, name=f"a_{i}_{s}")
            d[i, s] = model.addVar(vtype="C", lb=0.0, name=f"d_{i}_{s}")

    # x[i, j, s]: 駅sを出発する時点で、列車iが列車jより先に出発するとき 1 (バイナリ)
    # これにより、駅sからs+1の区間をどちらが先に走るかも決まる
    x = {}
    for i in TRAINS:
        for j in TRAINS:
            if i != j:
                for s in STATIONS[:-1]:
                    x[i, j, s] = model.addVar(vtype="B", name=f"x_{i}_{j}_{s}")

    # ---- 制約定義 ----
    for i in TRAINS:
        # 始発駅の出発時刻制限
        model.addCons(d[i, 0] >= RELEASE_TIMES[i], name=f"release_{i}")
        
        # 始発駅の到着時刻は出発と同一とする (ダミー)
        model.addCons(a[i, 0] == d[i, 0], name=f"init_arrival_{i}")

        # 1. 走行時間制約
        t_type = "Express" if "Express" in i else "Local"
        for s in STATIONS[:-1]:
            run_t = RUN_TIMES[t_type, s]
            model.addCons(
                a[i, s+1] >= d[i, s] + run_t,
                name=f"run_time_{i}_{s}"
            )

        # 2. 停車時間制約 (中間駅での最小停車)
        for s in STATIONS[1:-1]:
            model.addCons(
                d[i, s] >= a[i, s] + MIN_STOP,
                name=f"stop_time_{i}_{s}"
            )

    # 3. 追い越しとヘッドウェイ（安全間隔）制約
    for s in STATIONS[:-1]:
        for i in TRAINS:
            for j in TRAINS:
                if i != j:
                    # 順序変数の排他関係
                    if i < j:
                        model.addCons(
                            x[i, j, s] + x[j, i, s] == 1,
                            name=f"order_excl_{i}_{j}_{s}"
                        )
                    
                    # 列車 i が先に駅 s を出発する場合 (x[i,j,s]=1)
                    # 列車 j の出発は 列車 i の出発から最低 HEADWAY 分遅れる
                    # かつ、次の駅 s+1 への到着も最低 HEADWAY 分遅れる
                    model.addCons(
                        d[j, s] >= d[i, s] + HEADWAY - BIG_M * (1 - x[i, j, s]),
                        name=f"headway_dep_{i}_{j}_{s}"
                    )
                    model.addCons(
                        a[j, s+1] >= a[i, s+1] + HEADWAY - BIG_M * (1 - x[i, j, s]),
                        name=f"headway_arr_{i}_{j}_{s}"
                    )

    # 4. 順序の保存（追い越し設備のない区間での順序固定）
    # この簡略モデルでは、駅間での追い越しは不可能であり、駅でのみ追い越し（待避）ができるため、
    # 駅s+1の出発時点での順序 x[i,j,s+1] は、駅s出発時の順序 x[i,j,s] から変更できる（駅での追い越し）。
    # ただし、始発から終着までの整合性を取るため、特段追加の制約は不要（各駅での到着・出発のヘッドウェイが満たされれば、駅内での追い越しとして成立する）。

    # ---- 目的関数 ----
    # 全列車の終着駅到着時刻の総和を最小化 (総所要時間・遅延の最小化)
    end_s = STATIONS[-1]
    total_travel_time = quicksum(a[i, end_s] for i in TRAINS)
    model.setObjective(total_travel_time, "minimize")

    model.data = {"a": a, "d": d, "x": x}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Total Arrival Time: {model.getObjVal():.2f} 分")
        d = model.data

        TRAINS = ["Local_1", "Express_2", "Local_3"]
        STATIONS = [0, 1, 2, 3]

        print("\n--- Train Timetable ---")
        for i in TRAINS:
            print(f"\nSchedule for {i}:")
            for s in STATIONS:
                arr = model.getVal(d["a"][i, s])
                dep = model.getVal(d["d"][i, s])
                if s == 0:
                    print(f"  Station {s}: Departs at {dep:5.1f} min")
                elif s == STATIONS[-1]:
                    print(f"  Station {s}: Arrives at {arr:5.1f} min")
                else:
                    print(f"  Station {s}: Arrives at {arr:5.1f} min | Departs at {dep:5.1f} min")

        # 追い越しが発生したかどうかの判定
        print("\n--- Overtaking Analysis ---")
        for s in STATIONS[:-1]:
            # 各駅出発時の順序を表示
            order = []
            # トポロジカルソートのような簡易順序付け
            for i in TRAINS:
                before_count = sum(1 for j in TRAINS if i != j and model.getVal(d["x"][j, i, s]) > 0.5)
                order.append((before_count, i))
            order.sort()
            ordered_trains = [train for _, train in order]
            print(f"  Station {s} Departure Order: " + " -> ".join(ordered_trains))

if __name__ == "__main__":
    main()
