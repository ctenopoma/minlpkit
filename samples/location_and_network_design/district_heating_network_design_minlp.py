"""地域熱供給網におけるプラント配置・パイプライン敷設・サイジング同時最適化 (MINLP)

複数の需要家が存在する地域において、どこに熱源プラントを配置し、
どのルートでパイプラインを敷設し、どの配管径を選択するかを同時に決定する
ネットワークトポロジー設計問題です。
配管径を太くすれば初期投資は増えますが、流体の圧力損失（流量の2乗に比例し、径の5乗に反比例）
が減るため運用時のポンプ動力が下がります。
離散的な設計変数（配置、敷設、配管径選択）と、
非線形な物理特性（圧力損失、熱輸送）を統合した高度な MINLP モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("District_Heating_Network_Design")

    # ---- データ設定 ----
    # ノード: 0,1,2,3,4 (0と1はプラント候補地、2,3,4は需要家)
    NODES = [0, 1, 2, 3, 4]
    PLANT_CANDIDATES = [0, 1]
    CONSUMERS = {2: 300.0, 3: 400.0, 4: 200.0} # 熱需要 [kW]

    # パイプライン敷設候補エッジ (有向グラフ化)
    EDGES = [(0, 2), (0, 3), (1, 3), (1, 4), (2, 3), (3, 4), (3, 2), (4, 3)]
    
    # 距離 [m]
    LENGTH = {
        (0, 2): 500, (0, 3): 800, (1, 3): 600, (1, 4): 400,
        (2, 3): 300, (3, 4): 300, (3, 2): 300, (4, 3): 300
    }

    # 配管径の選択肢 [m] と、メートルあたりの敷設コスト [$/m]
    DIAMETERS = ["D1", "D2", "D3"]
    D_VAL = {"D1": 0.1, "D2": 0.15, "D3": 0.2}
    D_COST = {"D1": 100, "D2": 180, "D3": 250}

    # プラント建設コスト
    PLANT_FIXED_COST = 50000.0

    # 物理パラメータ
    CP = 4.18  # 比熱 [kJ/(kg K)]
    DELTA_T = 20.0  # 供給-還流 温度差 [℃]
    RHO = 1000.0 # 密度 [kg/m^3]
    # 摩擦係数などのまとめた定数 (圧力損失 dP = K_f * L * m^2 / D^5)
    # Darcy-Weisbachを変形したもの。係数は適当にスケーリング
    K_F = 0.0005 

    # 運用期間の重み (ポンプ動力コストを初期投資と同じスケールにするための年化係数)
    OP_WEIGHT = 8760 * 0.15  # 時間 * 単価

    # ---- 変数定義 ----
    # プラント配置フラグ
    y_plant = {n: model.addVar(vtype="B", name=f"y_plant_{n}") for n in PLANT_CANDIDATES}
    # プラント供給熱量 [kW]
    q_plant = {n: model.addVar(vtype="C", lb=0.0, ub=2000.0, name=f"q_plant_{n}") for n in PLANT_CANDIDATES}

    # パイプ敷設・径選択フラグ (z[e, d] == 1 ならエッジeに径dを敷設)
    z = {}
    for e in EDGES:
        for d in DIAMETERS:
            z[e, d] = model.addVar(vtype="B", name=f"z_{e[0]}_{e[1]}_{d}")
            
    # パイプが敷設されているかどうかのフラグ
    y_edge = {e: model.addVar(vtype="B", name=f"y_edge_{e[0]}_{e[1]}") for e in EDGES}

    # 質量流量 m[e] [kg/s]
    m_flow = {e: model.addVar(vtype="C", lb=0.0, ub=100.0, name=f"m_{e[0]}_{e[1]}") for e in EDGES}

    # 圧力損失 dp[e] と ポンプ動力 w_pump[e]
    dp = {e: model.addVar(vtype="C", lb=0.0, name=f"dp_{e[0]}_{e[1]}") for e in EDGES}
    w_pump = {e: model.addVar(vtype="C", lb=0.0, name=f"w_{e[0]}_{e[1]}") for e in EDGES}

    # ---- 制約定義 ----
    for n in PLANT_CANDIDATES:
        model.addCons(q_plant[n] <= 2000.0 * y_plant[n])

    for e in EDGES:
        # 径は高々1つしか選べない
        model.addCons(quicksum(z[e, d] for d in DIAMETERS) == y_edge[e])
        
        # 敷設されていないパイプには流量が流れない
        model.addCons(m_flow[e] <= 100.0 * y_edge[e])
        
        # 圧力損失制約 (非線形性)
        # dp = K_f * L * m^2 / D^5
        # zによってDが決まるため、ビッグM法または方程式の切り替えを行う
        for d in DIAMETERS:
            d_val5 = D_VAL[d] ** 5
            coef = K_F * LENGTH[e] / d_val5
            # z=1 のとき dp >= coef * m^2 を満たすようにする
            # (緩和のため不等式。目的関数で最小化されるため等式に張り付く)
            model.addCons(dp[e] >= coef * m_flow[e] * m_flow[e] - 100000.0 * (1 - z[e, d]))

        # ポンプ動力 (W = dp * m / rho) ※ m と dp の積なので非線形
        model.addCons(w_pump[e] >= (dp[e] * m_flow[e]) / RHO)

    # 質量保存とエネルギーバランス
    # 需要流量: m_req = Q / (CP * DELTA_T)
    m_req = {n: CONSUMERS[n] / (CP * DELTA_T) for n in CONSUMERS}

    for n in NODES:
        in_flow = quicksum(m_flow[e] for e in EDGES if e[1] == n)
        out_flow = quicksum(m_flow[e] for e in EDGES if e[0] == n)
        
        if n in PLANT_CANDIDATES:
            # プラントノード: 送出流量 = q_plant / (CP * dT)
            model.addCons(out_flow - in_flow == q_plant[n] / (CP * DELTA_T))
        else:
            # 需要家ノード: 流入 - 流出 == 需要
            model.addCons(in_flow - out_flow == m_req[n])

    # 少なくとも1つはプラントを建てる
    model.addCons(quicksum(y_plant[n] for n in PLANT_CANDIDATES) >= 1)

    # ---- 目的関数 ----
    # プラント建設費 + パイプ敷設費 + ポンプ動力運用費(年化)
    cost_plant = quicksum(PLANT_FIXED_COST * y_plant[n] for n in PLANT_CANDIDATES)
    cost_pipe = quicksum(LENGTH[e] * D_COST[d] * z[e, d] for e in EDGES for d in DIAMETERS)
    cost_pump = quicksum(w_pump[e] * OP_WEIGHT for e in EDGES)

    model.setObjective(cost_plant + cost_pipe + cost_pump, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Network Cost: ${m.getObjVal():.2f}")
