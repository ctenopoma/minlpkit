"""予防保全と生産の同時スケジューリング (Simultaneous Production and Maintenance Scheduling)

工場内の複数の製造ラインにおいて、製品の生産計画（ジョブ割り当て）と、
装置の「連続稼働時間制限（摩耗による劣化防止）」に基づく「予防保全（メンテナンス）計画」を
同時に最適化します。
メンテナンスを実施すると装置の累積稼働時間は 0 にリセットされますが、その間生産は停止します。
生産遅延ペナルティとメンテナンスコストの合計を最小化する混合整数線形計画法 (MILP) モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Production_and_Maintenance_Scheduling")

    # ---- データ設定 ----
    # タイムホライズン (16期間)
    T = 16
    PERIODS = list(range(1, T + 1))

    MACHINES = ["Machine_A", "Machine_B"]

    # マシンの最大連続稼働時間（これを超える前にメンテナンスが必要）
    MAX_RUN_TIME = {
        "Machine_A": 5,
        "Machine_B": 4,
    }

    # メンテナンスにかかる時間 (期間数) とコスト
    MAINT_DURATION = 2
    MAINT_COST = {
        "Machine_A": 15.0,
        "Machine_B": 10.0,
    }

    # ジョブ需要 (必要な処理期間数)
    JOBS = {
        "Job_1": {"demand": 4, "penalty": 5.0},
        "Job_2": {"demand": 6, "penalty": 4.0},
        "Job_3": {"demand": 3, "penalty": 6.0},
    }

    # 十分大きな数 Big-M
    BIG_M = 20.0

    # ---- 変数定義 ----
    # x[j, m, t]: 期間tにマシンmでジョブjを処理しているとき1 (バイナリ)
    x = {}
    for j in JOBS:
        for m in MACHINES:
            for t in PERIODS:
                x[j, m, t] = model.addVar(vtype="B", name=f"x_{j}_{m}_{t}")

    # y[m, t]: 期間tにマシンmでメンテナンスを開始するとき1 (バイナリ)
    y = {}
    for m in MACHINES:
        for t in PERIODS:
            y[m, t] = model.addVar(vtype="B", name=f"y_{m}_{t}")

    # u[m, t]: 期間tにマシンmがメンテナンス中であるとき1 (バイナリ)
    u = {}
    for m in MACHINES:
        for t in PERIODS:
            u[m, t] = model.addVar(vtype="B", name=f"u_{m}_{t}")

    # w[m, t]: 期間t終了時点におけるマシンmの「現在の連続稼働時間」 (連続)
    w = {}
    for m in MACHINES:
        for t in [0] + PERIODS:
            w[m, t] = model.addVar(vtype="C", lb=0.0, name=f"w_{m}_{t}")

    # s[j]: ジョブjの未充足量 (ペナルティ計算用) (連続)
    s = {}
    for j in JOBS:
        s[j] = model.addVar(vtype="C", lb=0.0, name=f"s_{j}")

    # ---- 制約定義 ----
    # 初期状態
    for m in MACHINES:
        model.addCons(w[m, 0] == 0.0, name=f"init_wear_{m}")

    # 1. メンテナンス状態 u[m, t] と開始フラグ y[m, t] の関係
    # メンテナンス開始から MAINT_DURATION 期間はメンテナンス中となる
    for m in MACHINES:
        for t in PERIODS:
            # u[m, t] は直近の MAINT_DURATION 期間の y[m, theta] の和に等しい
            maint_active = []
            for theta in range(max(1, t - MAINT_DURATION + 1), t + 1):
                maint_active.append(y[m, theta])
            model.addCons(
                u[m, t] == quicksum(maint_active),
                name=f"maint_active_relation_{m}_{t}"
            )

    # 2. マシンの排他制御
    # 各期間において、マシンは「ジョブ処理」を行うか、「メンテナンス中」であるか、あるいは何もしない
    for m in MACHINES:
        for t in PERIODS:
            model.addCons(
                quicksum(x[j, m, t] for j in JOBS) + u[m, t] <= 1,
                name=f"machine_exclusion_{m}_{t}"
            )

    # 3. 連続稼働時間 w[m, t] のダイナミクス
    # - メンテナンス中(u[m,t]=1) ならば、連続稼働時間は 0 にリセット
    # - そうでなければ、前期間の値に、今期間にジョブ処理を行ったか(動かしたか)を足す
    for m in MACHINES:
        for t in PERIODS:
            # メンテナンス中のリセット制約
            model.addCons(
                w[m, t] <= MAX_RUN_TIME[m] * (1 - u[m, t]),
                name=f"wear_reset_maint_{m}_{t}"
            )
            # 稼働時間の蓄積制約 (u[m,t] = 0 のときは w[m,t] >= w[m,t-1] + sum(x[j,m,t]))
            model.addCons(
                w[m, t] >= w[m, t - 1] + quicksum(x[j, m, t] for j in JOBS) - BIG_M * u[m, t],
                name=f"wear_accumulation_{m}_{t}"
            )
            # 連続稼働時間の上限
            model.addCons(
                w[m, t] <= MAX_RUN_TIME[m],
                name=f"wear_limit_{m}_{t}"
            )

    # 4. 需要充足と未充足量の定義
    for j, jd in JOBS.items():
        model.addCons(
            quicksum(x[j, m, t] for m in MACHINES for t in PERIODS) + s[j] >= jd["demand"],
            name=f"demand_deficit_{j}"
        )

    # 5. 境界付近でのメンテナンスの回り込み防止 (タイムホライズン最後での開始)
    for m in MACHINES:
        for t in range(T - MAINT_DURATION + 2, T + 1):
            model.addCons(y[m, t] == 0, name=f"no_late_maint_{m}_{t}")

    # ---- 目的関数 ----
    # 総コスト = メンテナンス実施コスト + 生産未充足ペナルティ
    cost_maint = quicksum(y[m, t] * MAINT_COST[m] for m in MACHINES for t in PERIODS)
    cost_penalty = quicksum(s[j] * jd["penalty"] for j, jd in JOBS.items())
    model.setObjective(cost_maint + cost_penalty, "minimize")

    model.data = {"x": x, "y": y, "u": u, "w": w, "s": s}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Total Cost: {model.getObjVal():.2f}")
        d = model.data

        # ガントチャート形式での表示
        JOBS = ["Job_1", "Job_2", "Job_3"]
        MACHINES = ["Machine_A", "Machine_B"]
        print("\n--- Schedule Gantt Chart ---")
        for m in MACHINES:
            row = []
            for t in range(1, 17):
                wear = model.getVal(d["w"][m, t])
                if model.getVal(d["u"][m, t]) > 0.5:
                    row.append("[Mnt]")
                else:
                    active_job = None
                    for j in JOBS:
                        if model.getVal(d["x"][j, m, t]) > 0.5:
                            active_job = j
                            break
                    if active_job:
                        row.append(f"[{active_job[-1]}:{int(wear)}]")
                    else:
                        row.append("[ - ]")
            print(f"{m:9s}: " + " ".join(row))

        print("\n--- Production Deficits ---")
        for j in JOBS:
            def_v = model.getVal(d["s"][j])
            print(f"  {j}: deficit = {def_v:.1f}")

if __name__ == "__main__":
    main()
