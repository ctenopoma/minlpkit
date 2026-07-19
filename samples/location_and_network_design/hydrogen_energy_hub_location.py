"""水素エネルギーハブ (再エネ・電解槽・貯蔵) 最適配置・サイジングモデル (MINLP)

再生可能エネルギー（太陽光・風力）の出力変動を吸収し、
電力と水素を安定供給するための「水素エネルギーハブ」の設備構成を最適化します。
複数のサイトから、どこに太陽光、風力、水電解槽（Electrolyzer）、水素タンク、
および燃料電池（Fuel Cell）を配置し、どれだけの容量を持たせるかを決定します。
電解槽や燃料電池の非線形な効率特性（部分負荷特性）と、
水素・電力の需給バランス（時間変動）を組み合わせた高度な配置・サイジング問題です。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Hydrogen_Energy_Hub_Location")

    # ---- データ設定 ----
    SITES = ["SiteA", "SiteB"]
    T = 6
    TIME_STEPS = list(range(T))

    # 各サイトの再エネポテンシャルと需要 (簡易化のためT=6)
    # [kW]
    DEMAND_ELEC = {"SiteA": [100, 150, 120, 130, 180, 150], "SiteB": [50, 60, 50, 70, 80, 60]}
    DEMAND_H2 = {"SiteA": [10, 10, 10, 10, 10, 10], "SiteB": [20, 20, 20, 20, 20, 20]} # [kg/h]

    # 容量あたりの発電量プロファイル (1kW容量あたり)
    PV_PROFILE = [0.0, 0.2, 0.8, 1.0, 0.5, 0.0]
    WIND_PROFILE = [0.5, 0.6, 0.4, 0.3, 0.7, 0.8]

    # コストパラメータ [k$]
    COST_PV = 1.0       # k$/kW
    COST_WIND = 1.5     # k$/kW
    COST_ELY = 2.0      # 電解槽 k$/kW
    COST_TANK = 0.5     # 水素タンク k$/kg
    COST_FC = 2.5       # 燃料電池 k$/kW

    # サイト間の連系線コスト（電力、水素パイプ）
    LINE_COST = 50.0  # k$ (敷設バイナリ)

    # 物理特性
    # 電解槽の水素製造 [kg/h] = P_ely [kW] / E_spec [kWh/kg]
    # E_spec は非線形: 部分負荷で効率が下がる (E_specが上がる)
    # 簡易的に H2_prod = a * P_ely - b * P_ely^2 とする
    ELY_A, ELY_B = 0.02, 0.00001
    
    # 燃料電池の発電 [kW] = H2_cons [kg/h] * LHV * EFF
    # EFFも非線形だが、ここでは線形化 (1kg/h -> 15kW)
    FC_RATE = 15.0

    # ---- 変数定義 ----
    # 1. 設備容量 (サイジング)
    cap_pv = {s: model.addVar(vtype="C", lb=0.0, ub=1000.0, name=f"cap_pv_{s}") for s in SITES}
    cap_wind = {s: model.addVar(vtype="C", lb=0.0, ub=1000.0, name=f"cap_wind_{s}") for s in SITES}
    cap_ely = {s: model.addVar(vtype="C", lb=0.0, ub=500.0, name=f"cap_ely_{s}") for s in SITES}
    cap_tank = {s: model.addVar(vtype="C", lb=0.0, ub=200.0, name=f"cap_tank_{s}") for s in SITES}
    cap_fc = {s: model.addVar(vtype="C", lb=0.0, ub=500.0, name=f"cap_fc_{s}") for s in SITES}

    # 2. ネットワーク (サイト間連系)
    y_elec_line = model.addVar(vtype="B", name="y_elec_line")
    y_h2_pipe = model.addVar(vtype="B", name="y_h2_pipe")

    # 3. 運用変数
    # 電力
    p_ely = {}
    p_fc = {}
    p_trans = {} # SiteA -> SiteB
    for s in SITES:
        for t in TIME_STEPS:
            p_ely[s, t] = model.addVar(vtype="C", lb=0.0, name=f"p_ely_{s}_{t}")
            p_fc[s, t] = model.addVar(vtype="C", lb=0.0, name=f"p_fc_{s}_{t}")
    for t in TIME_STEPS:
        p_trans[t] = model.addVar(vtype="C", lb=-1000.0, ub=1000.0, name=f"p_trans_{t}")

    # 水素
    h2_prod = {}
    h2_cons = {}
    soc_tank = {}
    h2_trans = {} # SiteA -> SiteB
    for s in SITES:
        for t in range(T + 1):
            soc_tank[s, t] = model.addVar(vtype="C", lb=0.0, name=f"soc_{s}_{t}")
        for t in TIME_STEPS:
            h2_prod[s, t] = model.addVar(vtype="C", lb=0.0, name=f"h2_prod_{s}_{t}")
            h2_cons[s, t] = model.addVar(vtype="C", lb=0.0, name=f"h2_cons_{s}_{t}")
    for t in TIME_STEPS:
        h2_trans[t] = model.addVar(vtype="C", lb=-500.0, ub=500.0, name=f"h2_trans_{t}")

    # 系統買電
    p_buy = { (s, t): model.addVar(vtype="C", lb=0.0, name=f"p_buy_{s}_{t}") for s in SITES for t in TIME_STEPS }

    # ---- 制約定義 ----
    for s in SITES:
        model.addCons(soc_tank[s, 0] == 0.0)

        for t in TIME_STEPS:
            # 容量制約
            model.addCons(p_ely[s, t] <= cap_ely[s])
            model.addCons(p_fc[s, t] <= cap_fc[s])
            model.addCons(soc_tank[s, t] <= cap_tank[s])
            model.addCons(soc_tank[s, t+1] <= cap_tank[s])

            # 電解槽 非線形特性 (2次)
            # h2_prod = A * p_ely - B * p_ely^2
            model.addCons(h2_prod[s, t] == ELY_A * p_ely[s, t] - ELY_B * (p_ely[s, t] * p_ely[s, t]))
            
            # 燃料電池
            model.addCons(p_fc[s, t] == h2_cons[s, t] * FC_RATE)

            # 再エネ発電量
            gen_pv = cap_pv[s] * PV_PROFILE[t]
            gen_wind = cap_wind[s] * WIND_PROFILE[t]

            # 電力バランス
            # 供給(PV + Wind + FC + Buy + Trans_in) = 需要(Demand + Ely + Trans_out)
            in_trans = p_trans[t] if s == "SiteB" else -p_trans[t]
            model.addCons(
                gen_pv + gen_wind + p_fc[s, t] + p_buy[s, t] + in_trans ==
                DEMAND_ELEC[s][t] + p_ely[s, t]
            )

            # 水素バランス (タンクダイナミクス)
            in_h2 = h2_trans[t] if s == "SiteB" else -h2_trans[t]
            model.addCons(
                soc_tank[s, t+1] == soc_tank[s, t] + h2_prod[s, t] - h2_cons[s, t] - DEMAND_H2[s][t] + in_h2
            )

    # ネットワーク制約 (連系線がなければ送受電・送受水素不可)
    BIG_M_P = 1000.0
    BIG_M_H = 500.0
    for t in TIME_STEPS:
        model.addCons(p_trans[t] <= BIG_M_P * y_elec_line)
        model.addCons(p_trans[t] >= -BIG_M_P * y_elec_line)
        
        model.addCons(h2_trans[t] <= BIG_M_H * y_h2_pipe)
        model.addCons(h2_trans[t] >= -BIG_M_H * y_h2_pipe)

    # ---- 目的関数 ----
    # 設備投資コスト + 買電コスト (運用費)
    cost_inv = quicksum(
        COST_PV * cap_pv[s] + COST_WIND * cap_wind[s] + 
        COST_ELY * cap_ely[s] + COST_TANK * cap_tank[s] + COST_FC * cap_fc[s]
        for s in SITES
    ) + LINE_COST * y_elec_line + LINE_COST * y_h2_pipe

    cost_op = quicksum(p_buy[s, t] * 0.2 for s in SITES for t in TIME_STEPS) * 365 # 年間換算イメージ

    model.setObjective(cost_inv + cost_op, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Hub Design Cost: ${m.getObjVal():.2f}")
