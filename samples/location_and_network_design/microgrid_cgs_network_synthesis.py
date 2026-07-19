"""分散型マイクログリッドにおける熱電融通ネットワークとコージェネ配置 (MINLP)

複数のビルや施設からなる地域コミュニティ（マイクログリッド）において、
どのビルにコージェネレーションシステム（CGS）やボイラーを設置するか、
およびビル間に「電力融通線（Microgrid Cable）」と「熱融通管（Heat Pipe）」を
敷設するかどうか（トポロジー設計）を同時に最適化します。
CGSの部分負荷効率（2次関数）を考慮しつつ、ビル間でエネルギーを融通することで、
コミュニティ全体のCO2排出量や総コストを最小化する複雑なスーパー構造最適化です。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Microgrid_CGS_Network_Synthesis")

    # ---- データ設定 ----
    # 3つのビル
    BUILDINGS = ["B1", "B2", "B3"]
    # 時間 (簡易的に代表的な4時間)
    TIME_STEPS = [0, 1, 2, 3]

    # 需要 (電力, 熱) [kW]
    # B1: オフィス (昼に電力が大きい)
    # B2: ホテル (夜・朝に熱が大きい)
    # B3: 商業施設 (昼～夕に電力・熱がそこそこ)
    D_ELEC = {
        "B1": [50, 150, 200, 50],
        "B2": [60, 40, 50, 80],
        "B3": [30, 100, 150, 60]
    }
    D_HEAT = {
        "B1": [10, 20, 20, 10],
        "B2": [100, 60, 50, 120],
        "B3": [20, 50, 60, 30]
    }

    # 機器の選択肢 (各ビルに設置可能)
    CGS_CAP = 250.0   # CGS最大発電容量 [kW]
    BOIL_CAP = 200.0  # ボイラー最大熱容量 [kW]

    CGS_COST = 300.0  # 設置コスト (k$)
    BOIL_COST = 50.0  # 設置コスト (k$)

    # ネットワーク構築の候補エッジ (無向グラフだが有向として扱う)
    EDGES = [("B1", "B2"), ("B2", "B3"), ("B1", "B3")]
    ELEC_LINE_COST = 50.0
    HEAT_PIPE_COST = 80.0

    # CGSの非線形特性
    # 発電効率: 負荷率が低いと悪化する。Fuel = a * P^2 + b * P + c * y
    CGS_A, CGS_B, CGS_C = 0.005, 2.0, 10.0
    # 排熱回収は燃料消費の約40%とする
    HEAT_RECOVERY_RATE = 0.4

    # ボイラー効率
    BOIL_EFF = 0.8

    # 運用コスト (重み)
    GAS_PRICE = 0.05   # $/kWh
    GRID_PRICE = 0.15  # $/kWh

    # ---- 変数定義 ----
    # 1. 設置変数 (バイナリ)
    y_cgs = {b: model.addVar(vtype="B", name=f"y_cgs_{b}") for b in BUILDINGS}
    y_boil = {b: model.addVar(vtype="B", name=f"y_boil_{b}") for b in BUILDINGS}

    z_elec = {e: model.addVar(vtype="B", name=f"z_elec_{e[0]}_{e[1]}") for e in EDGES}
    z_heat = {e: model.addVar(vtype="B", name=f"z_heat_{e[0]}_{e[1]}") for e in EDGES}

    # 2. 運用変数
    p_cgs = {}
    fuel_cgs = {}
    q_cgs = {}
    q_boil = {}
    p_grid = {}

    p_trans = {}  # 融通電力 (e[0] -> e[1])
    q_trans = {}  # 融通熱   (e[0] -> e[1])

    for b in BUILDINGS:
        for t in TIME_STEPS:
            p_cgs[b, t] = model.addVar(vtype="C", lb=0.0, ub=CGS_CAP, name=f"p_cgs_{b}_{t}")
            fuel_cgs[b, t] = model.addVar(vtype="C", lb=0.0, name=f"fuel_cgs_{b}_{t}")
            q_cgs[b, t] = model.addVar(vtype="C", lb=0.0, name=f"q_cgs_{b}_{t}")
            q_boil[b, t] = model.addVar(vtype="C", lb=0.0, ub=BOIL_CAP, name=f"q_boil_{b}_{t}")
            p_grid[b, t] = model.addVar(vtype="C", lb=0.0, name=f"p_grid_{b}_{t}")

    for e in EDGES:
        for t in TIME_STEPS:
            # 融通方向は双方向を許容するため lb=-1000, ub=1000
            p_trans[e, t] = model.addVar(vtype="C", lb=-1000.0, ub=1000.0, name=f"p_trans_{e[0]}_{e[1]}_{t}")
            q_trans[e, t] = model.addVar(vtype="C", lb=-1000.0, ub=1000.0, name=f"q_trans_{e[0]}_{e[1]}_{t}")

    # ---- 制約定義 ----
    for b in BUILDINGS:
        for t in TIME_STEPS:
            # 機器容量上限 (非設置時は0)
            model.addCons(p_cgs[b, t] <= CGS_CAP * y_cgs[b])
            model.addCons(q_boil[b, t] <= BOIL_CAP * y_boil[b])

            # CGSの非線形効率
            # Fuel = A * p^2 + B * p + C * y
            model.addCons(fuel_cgs[b, t] == CGS_A * p_cgs[b, t] * p_cgs[b, t] + CGS_B * p_cgs[b, t] + CGS_C * y_cgs[b])
            # 排熱
            model.addCons(q_cgs[b, t] == fuel_cgs[b, t] * HEAT_RECOVERY_RATE)

            # ノードバランス (電力)
            in_elec = p_grid[b, t] + p_cgs[b, t]
            for e in EDGES:
                if e[0] == b:
                    in_elec -= p_trans[e, t]  # 送り出す
                elif e[1] == b:
                    in_elec += p_trans[e, t]  # 受け取る
            model.addCons(in_elec == D_ELEC[b][t])

            # ノードバランス (熱)
            in_heat = q_cgs[b, t] + q_boil[b, t]
            for e in EDGES:
                if e[0] == b:
                    in_heat -= q_trans[e, t]
                elif e[1] == b:
                    in_heat += q_trans[e, t]
            model.addCons(in_heat == D_HEAT[b][t])

    # ネットワーク融通のバイナリ制約 (繋がっていなければ融通0)
    BIG_M_P = 1000.0
    BIG_M_Q = 1000.0
    for e in EDGES:
        for t in TIME_STEPS:
            model.addCons(p_trans[e, t] <= BIG_M_P * z_elec[e])
            model.addCons(p_trans[e, t] >= -BIG_M_P * z_elec[e])
            
            model.addCons(q_trans[e, t] <= BIG_M_Q * z_heat[e])
            model.addCons(q_trans[e, t] >= -BIG_M_Q * z_heat[e])

    # ---- 目的関数 ----
    # 設備コスト(年化イメージ) + 運用コスト
    cost_inv = quicksum(CGS_COST * y_cgs[b] + BOIL_COST * y_boil[b] for b in BUILDINGS) \
             + quicksum(ELEC_LINE_COST * z_elec[e] + HEAT_PIPE_COST * z_heat[e] for e in EDGES)

    # 運用コスト (1日分とみなして拡張する係数をかける)
    cost_op = quicksum(
        (fuel_cgs[b, t] + q_boil[b, t] / BOIL_EFF) * GAS_PRICE + p_grid[b, t] * GRID_PRICE
        for b in BUILDINGS for t in TIME_STEPS
    ) * 365

    model.setObjective(cost_inv + cost_op / 1000.0, "minimize")  # スケールをk$に合わせる
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Microgrid Synthesis Cost: ${m.getObjVal():.2f}k")
