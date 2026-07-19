"""データセンターのITジョブと冷却・電力システムの連成最適化 (MINLP)

大量の電力を消費するデータセンターにおいて、計算ジョブ（バッチ処理）の
スケジューリングと冷却設備の運用を同時に最適化します。
サーバーの消費電力は計算負荷に対して非線形（2次関数）に増加し、それが発熱となります。
冷却にはチラー（冷却機）とフリークーリング（外気冷房）を併用します。
外気温度(T_amb)が低い夜間はチラーのCOPが高く、フリークーリングも有効なため、
非即時性のジョブを夜間にシフトすることで、トータル消費電力とコストを削減します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("DataCenter_Cooling_Power_MINLP")

    # ---- データ設定 (24時間) ----
    T = 24
    TIME_STEPS = list(range(T))

    # 外気温度 [℃]
    T_AMB = [15, 14, 13, 13, 14, 15, 18, 22, 26, 28, 
             30, 32, 32, 31, 29, 27, 24, 22, 20, 19, 
             17, 16, 16, 15]

    # ベースラインIT負荷（動かせない対話型通信など） [kW]
    BASE_IT_LOAD = [500 + 100 * (t % 12) for t in TIME_STEPS]

    # バッチジョブ (シフト可能な計算負荷)
    # job_id: (総必要計算量 [MIPS等], 締切時刻(0~24))
    BATCH_JOBS = {
        "Job1": (1000.0, 12),  # 昼までに終わらせる
        "Job2": (2500.0, 24),  # 1日の中でいつでも良い（夜間推奨）
        "Job3": (1500.0, 24)
    }

    # サーバー特性
    # 消費電力 = P_idle + C_1 * Load + C_2 * Load^2
    P_IDLE = 100.0
    C1 = 0.5
    C2 = 0.001
    MAX_LOAD_PER_STEP = 500.0  # 1ステップに処理できる最大計算量

    # 冷却システム特性
    # チラーのCOP: 外気が高いと悪化 (COP = 8.0 - 0.15 * T_amb)
    def get_cop(tamb):
        return max(2.0, 8.0 - 0.15 * tamb)
        
    # フリークーリング容量 (外気が15℃以下なら効果大、それ以上はゼロ)
    def get_free_cooling(tamb):
        return max(0.0, (18.0 - tamb) * 50.0)

    # 電力料金 [$/kWh]
    PRICE_BUY = [10.0 if t < 8 or t >= 22 else 20.0 for t in TIME_STEPS]

    # ---- 変数定義 ----
    # ジョブの割り当て
    # x[j, t]: ジョブ j を時刻 t で処理する量
    x = {}
    for j, (req, dl) in BATCH_JOBS.items():
        for t in TIME_STEPS:
            x[j, t] = model.addVar(vtype="C", lb=0.0, ub=MAX_LOAD_PER_STEP, name=f"x_{j}_{t}")

    # IT総負荷とサーバー電力
    it_load = {t: model.addVar(vtype="C", lb=0.0, name=f"it_load_{t}") for t in TIME_STEPS}
    p_it = {t: model.addVar(vtype="C", lb=0.0, name=f"p_it_{t}") for t in TIME_STEPS}

    # 冷却機器
    q_chiller = {t: model.addVar(vtype="C", lb=0.0, name=f"q_chiller_{t}") for t in TIME_STEPS}
    p_chiller = {t: model.addVar(vtype="C", lb=0.0, name=f"p_chiller_{t}") for t in TIME_STEPS}

    # 施設総電力
    p_total = {t: model.addVar(vtype="C", lb=0.0, name=f"p_total_{t}") for t in TIME_STEPS}

    # ---- 制約定義 ----
    # 1. ジョブ要件
    for j, (req, dl) in BATCH_JOBS.items():
        # 必要量の消化
        model.addCons(quicksum(x[j, t] for t in TIME_STEPS) == req, name=f"job_req_{j}")
        # 締切以降は割り当て不可
        for t in range(dl, T):
            if t < T:
                model.addCons(x[j, t] == 0.0, name=f"job_dl_{j}_{t}")

    for t in TIME_STEPS:
        # 2. IT負荷と非線形電力特性
        model.addCons(
            it_load[t] == BASE_IT_LOAD[t] + quicksum(x[j, t] for j in BATCH_JOBS),
            name=f"calc_it_load_{t}"
        )
        
        # p_it = P_IDLE + C1 * load + C2 * load^2
        model.addCons(
            p_it[t] == P_IDLE + C1 * it_load[t] + C2 * (it_load[t] * it_load[t]),
            name=f"p_it_curve_{t}"
        )

        # 3. 発熱と冷却バランス
        # IT消費電力 = そのまま発熱量(Q)になると仮定
        q_heat = p_it[t]
        
        # Q_heat = Q_chiller + Q_freecooling
        fc_cap = get_free_cooling(T_AMB[t])
        # チラーが負担すべき熱量 (非負)
        # q_chiller[t] >= q_heat - fc_cap
        model.addCons(q_chiller[t] >= q_heat - fc_cap, name=f"chiller_load_{t}")

        # チラー消費電力 = q_chiller / COP
        cop = get_cop(T_AMB[t])
        model.addCons(p_chiller[t] == q_chiller[t] / cop, name=f"chiller_power_{t}")

        # 4. 総電力
        model.addCons(p_total[t] == p_it[t] + p_chiller[t], name=f"p_total_def_{t}")

    # ---- 目的関数 ----
    # 総電力コストの最小化
    total_cost = quicksum(p_total[t] * PRICE_BUY[t] for t in TIME_STEPS)
    model.setObjective(total_cost, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Data Center Daily Cost: ${m.getObjVal():.2f}")
        for t in range(24):
            # 夜間(0-6)など安い時間・涼しい時間にJob2, Job3が寄っているか確認可能
            pass
