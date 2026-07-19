"""地域熱供給網 (District Heating Network) の詳細物理最適化モデル (MINLP)

熱源プラントから複数の需要家への熱供給ネットワークにおいて、
配管内の質量流量と温度のダイナミクス（エネルギー保存）、
および圧力損失（Darcy-Weisbach）とポンプ動力を詳細にモデル化します。
節点における流量と温度の混合（Bilinear）、圧力損失の非線形性（流量の2乗）、
熱損失の温度依存性を考慮した高度な混合整数非線形計画法 (MINLP) です。
総ポンプ動力と熱損失・燃料コストの合計を最小化します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("District_Heating_Detailed_Physics")

    # ---- データ設定 ----
    # ノード: 0=熱源(Source), 1,2=需要家(Consumers)
    NODES = [0, 1, 2]
    # エッジ(配管): (from, to) の有向グラフ
    EDGES = [(0, 1), (1, 2)]

    # 供給(Supply)ネットワークと還流(Return)ネットワークをそれぞれ解くが、
    # 簡易化のためSupply側のみの温度と圧力を追う（Return側は一定とする）
    T_RET = 50.0  # 還流温度 [℃] 一定と仮定

    # 熱需要 [kW]
    Q_DEMAND = {1: 500.0, 2: 300.0}

    # 配管パラメータ
    K_PRESSURE = {(0, 1): 0.5, (1, 2): 0.8}  # 圧力損失係数
    K_HEATLOSS = {(0, 1): 0.1, (1, 2): 0.1}  # 熱損失係数 [kW/℃]

    # 熱媒体(水)の比熱 [kJ/(kg K)]
    CP = 4.18 
    T_ENV = 10.0  # 外気温 [℃]

    # 境界条件
    T_SOURCE_MIN = 70.0
    T_SOURCE_MAX = 120.0
    PUMP_EFF = 0.7  # ポンプ効率

    # ---- 変数定義 ----
    # m[e]: エッジ e の質量流量 [kg/s]
    m_flow = {}
    for e in EDGES:
        m_flow[e] = model.addVar(vtype="C", lb=0.0, ub=100.0, name=f"m_{e[0]}_{e[1]}")

    # t_node[n]: ノード n の温度 [℃]
    t_node = {}
    for n in NODES:
        t_node[n] = model.addVar(vtype="C", lb=50.0, ub=T_SOURCE_MAX, name=f"t_{n}")

    # t_out[e]: エッジ e の出口温度 [℃] (熱損失考慮)
    t_out = {}
    for e in EDGES:
        t_out[e] = model.addVar(vtype="C", lb=50.0, ub=T_SOURCE_MAX, name=f"t_out_{e[0]}_{e[1]}")

    # dp[e]: エッジ e の圧力損失 [kPa]
    dp = {}
    for e in EDGES:
        dp[e] = model.addVar(vtype="C", lb=0.0, name=f"dp_{e[0]}_{e[1]}")

    # 熱源の生成熱量 [kW] とポンプ動力 [kW]
    q_source = model.addVar(vtype="C", lb=0.0, name="q_source")
    w_pump = model.addVar(vtype="C", lb=0.0, name="w_pump")

    # ---- 制約定義 ----
    # 1. 質量保存則
    # ノード0 (熱源): 供給流量 = sum(m[0, j])
    m_source = quicksum(m_flow[0, j] for j in NODES if (0, j) in EDGES)

    # 各需要家ノードにおける質量保存 (流入 = 流出 + 需要家消費流量)
    m_cons = {}
    for n in [1, 2]:
        m_in = quicksum(m_flow[i, n] for i in NODES if (i, n) in EDGES)
        m_out_edge = quicksum(m_flow[n, j] for j in NODES if (n, j) in EDGES)
        # 需要家の消費流量: m_cons[n] = Q_DEMAND[n] / (CP * (t_node[n] - T_RET))
        # -> 非線形: Q_DEMAND[n] == m_cons[n] * CP * (t_node[n] - T_RET)
        m_cons[n] = model.addVar(vtype="C", lb=0.0, name=f"m_cons_{n}")
        model.addCons(Q_DEMAND[n] == m_cons[n] * CP * (t_node[n] - T_RET), name=f"demand_heat_{n}")
        
        # 質量の釣り合い
        model.addCons(m_in == m_out_edge + m_cons[n], name=f"mass_balance_{n}")

    # 2. エネルギー保存則 (温度混合と熱損失)
    for e in EDGES:
        # 配管の熱損失 (簡易化: 出口温度 = 入口温度 - 損失分)
        # 厳密には指数減衰だが、ここでは線形近似 (Q_loss = K * (T_in - T_env))
        # CP * m_flow * (t_in - t_out) = K * (t_in - T_env)
        # -> 非線形双線形項 m_flow * (t_node[e[0]] - t_out[e])
        model.addCons(
            CP * m_flow[e] * (t_node[e[0]] - t_out[e]) == K_HEATLOSS[e] * (t_node[e[0]] - T_ENV),
            name=f"heat_loss_{e[0]}_{e[1]}"
        )

    for n in [1, 2]:
        # ノードでの完全混合 (エネルギー保存)
        # sum( m_e * t_out_e ) = (sum m_e) * t_node_n
        in_edges = [e for e in EDGES if e[1] == n]
        if len(in_edges) > 0:
            model.addCons(
                quicksum(m_flow[e] * t_out[e] for e in in_edges) == 
                quicksum(m_flow[e] for e in in_edges) * t_node[n],
                name=f"temp_mix_{n}"
            )

    # 3. 圧力損失 (Darcy-Weisbachの簡易化)
    # dp = K * m^2
    for e in EDGES:
        model.addCons(dp[e] == K_PRESSURE[e] * m_flow[e] * m_flow[e], name=f"pressure_loss_{e[0]}_{e[1]}")

    # 4. 熱源の総熱量とポンプ動力
    # Q_source = m_source * CP * (T_source - T_RET)
    model.addCons(q_source == m_source * CP * (t_node[0] - T_RET), name="source_heat")

    # W_pump = sum(m_e * dp_e) / (rho * eff)  (簡易化のため定数係数 c)
    # ここでは dp と m_flow の積 (これも非線形)
    C_PUMP = 0.001 / PUMP_EFF
    model.addCons(w_pump == quicksum(m_flow[e] * dp[e] for e in EDGES) * C_PUMP, name="pump_power")

    # ---- 目的関数 ----
    # 燃料費 (熱量比例) + 電力費 (ポンプ動力)
    COST_HEAT = 5.0
    COST_ELEC = 20.0
    model.setObjective(COST_HEAT * q_source + COST_ELEC * w_pump, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Cost: {m.getObjVal():.2f}")
