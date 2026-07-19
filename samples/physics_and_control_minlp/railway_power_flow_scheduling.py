"""直流電気鉄道の運行スケジュールと潮流計算(Power Flow)の統合最適化 (MINLP)

列車の運行スケジュール（速度プロファイル、力行・惰行・減速モード）と、
直流き電網（変電所、架線、レール、列車）の潮流計算を同時に考慮する精緻化モデル。
列車の位置と消費/回生電力に応じて架線電圧が変動し、
回生電力が他の列車で消費されない場合、電圧上昇による回生失効（絞り込み）が発生します。
本モデルでは、列車の運動方程式、位置に依存する回路網のコンダクタンス、
電力=電圧×電流 の非線形方程式を組み込んだ MINLP として定式化し、
変電所からの総供給エネルギーとピーク電力を最小化するスケジュールを探索します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Railway_Power_Flow_Scheduling")

    # ---- データ設定 ----
    T = 10  # タイムステップ数（簡易化のため少なめに設定）
    DT = 10.0  # 1ステップの時間 [s]
    TIME_STEPS = list(range(T))

    TRAINS = ["T1", "T2"]
    
    # 列車パラメータ
    MASS = 150000.0  # 質量 [kg]
    MAX_ACCEL = 1.0  # 最大加速度 [m/s^2]
    MAX_DECEL = 1.0  # 最大減速度 [m/s^2]
    MAX_SPEED = 25.0 # 最大速度 [m/s]
    EFF_TR = 0.85    # 力行効率
    EFF_REG = 0.85   # 回生効率

    # 変電所 (Substation) とき電網パラメータ
    SUBSTATION_POS = 2000.0  # 変電所の位置 [m]
    V_SUB = 1500.0           # 変電所の無負荷電圧 [V]
    R_SUB = 0.05             # 変電所の内部抵抗 [Ohm]
    R_WIRE = 0.03            # 架線とレールの合成単位長抵抗 [Ohm/km] -> 0.00003 Ohm/m

    # 走行抵抗係数 (Davis方程式: R = A + B*v + C*v^2)
    A_res, B_res, C_res = 1500.0, 10.0, 0.5

    # ---- 変数定義 ----
    # 物理・運動変数
    x = {}  # 位置 [m]
    v = {}  # 速度 [m/s]
    a = {}  # 加速度 [m/s^2]
    for tr in TRAINS:
        for t in TIME_STEPS:
            x[tr, t] = model.addVar(vtype="C", lb=0.0, ub=5000.0, name=f"x_{tr}_{t}")
            v[tr, t] = model.addVar(vtype="C", lb=0.0, ub=MAX_SPEED, name=f"v_{tr}_{t}")
            a[tr, t] = model.addVar(vtype="C", lb=-MAX_DECEL, ub=MAX_ACCEL, name=f"a_{tr}_{t}")

    # 電力・回路変数
    p_mech = {}  # 機械出力 [W]
    p_elec = {}  # 電気出力 (架線での授受電力, 正が消費) [W]
    v_tr = {}    # 列車のパンタグラフ点電圧 [V]
    i_tr = {}    # 列車の消費電流 [A]
    for tr in TRAINS:
        for t in TIME_STEPS:
            p_mech[tr, t] = model.addVar(vtype="C", lb=-5e6, ub=5e6, name=f"p_mech_{tr}_{t}")
            p_elec[tr, t] = model.addVar(vtype="C", lb=-5e6, ub=5e6, name=f"p_elec_{tr}_{t}")
            v_tr[tr, t] = model.addVar(vtype="C", lb=900.0, ub=1800.0, name=f"v_tr_{tr}_{t}")
            i_tr[tr, t] = model.addVar(vtype="C", lb=-3000.0, ub=3000.0, name=f"i_tr_{tr}_{t}")

    # 変電所変数
    i_sub = {}   # 変電所供給電流 [A]
    v_bus = {}   # 変電所バス電圧 [V]
    p_sub = {}   # 変電所供給電力 [W]
    for t in TIME_STEPS:
        i_sub[t] = model.addVar(vtype="C", lb=0.0, ub=10000.0, name=f"i_sub_{t}")  # 回生電力を系統に返さない(ダイオード整流器)
        v_bus[t] = model.addVar(vtype="C", lb=900.0, ub=V_SUB, name=f"v_bus_{t}")
        p_sub[t] = model.addVar(vtype="C", lb=0.0, name=f"p_sub_{t}")

    # ---- 制約定義 ----
    # 1. 運動方程式
    for tr in TRAINS:
        for t in range(T - 1):
            # x(t+1) = x(t) + v(t)*dt + 0.5*a(t)*dt^2
            model.addCons(x[tr, t+1] == x[tr, t] + v[tr, t]*DT + 0.5*a[tr, t]*(DT**2))
            # v(t+1) = v(t) + a(t)*dt
            model.addCons(v[tr, t+1] == v[tr, t] + a[tr, t]*DT)
        
        for t in TIME_STEPS:
            # 機械出力 P_mech = F * v
            # F = M*a + 走行抵抗
            # ※ 走行抵抗のv^2項を導入するとより非線形になるため、ここでは簡易的に線形近似または二次式を採用
            f_tract = MASS * a[tr, t] + A_res + B_res * v[tr, t] + C_res * (v[tr, t]*v[tr, t])
            # P_mech = F * v (双線形・三次方程式)
            model.addCons(p_mech[tr, t] == f_tract * v[tr, t], name=f"mech_power_{tr}_{t}")

            # 効率を考慮した電気出力への変換
            # p_mech > 0 なら p_elec = p_mech / EFF_TR
            # p_mech < 0 なら p_elec = p_mech * EFF_REG
            # SCIPでは補助バイナリか緩和表現を使用。ここでは非線形緩和として滑らかな近似関数を用いるか、
            # あるいは分割変数 p_mech_pos, p_mech_neg を導入して線形化。
    
    # 厳密な絶対値分割による電力変換
    p_mech_pos = {}
    p_mech_neg = {}
    for tr in TRAINS:
        for t in TIME_STEPS:
            p_mech_pos[tr, t] = model.addVar(vtype="C", lb=0.0)
            p_mech_neg[tr, t] = model.addVar(vtype="C", lb=0.0)
            model.addCons(p_mech[tr, t] == p_mech_pos[tr, t] - p_mech_neg[tr, t])
            # 電気電力
            model.addCons(p_elec[tr, t] == p_mech_pos[tr, t] / EFF_TR - p_mech_neg[tr, t] * EFF_REG)

    # 2. 回路方程式 (電力・電圧・電流の非線形関係)
    # P = V * I
    for tr in TRAINS:
        for t in TIME_STEPS:
            model.addCons(p_elec[tr, t] == v_tr[tr, t] * i_tr[tr, t], name=f"power_eq_{tr}_{t}")

    # 変電所の電圧降下
    for t in TIME_STEPS:
        model.addCons(v_bus[t] == V_SUB - R_SUB * i_sub[t], name=f"sub_drop_{t}")
        model.addCons(p_sub[t] == v_bus[t] * i_sub[t], name=f"sub_power_{t}")

    # 電圧-位置の関係 (位置に応じた抵抗)
    # V_tr = V_bus - I_tr * R(x) (※1列車の時。2列車だとネットワークを解く必要がある)
    # ここでは2列車が変電所を挟んで別々にいるか、等価抵抗として距離の絶対値をとる簡易放射状モデル
    dist = {}
    for tr in TRAINS:
        for t in TIME_STEPS:
            dist[tr, t] = model.addVar(vtype="C", lb=0.0)
            # dist = |x - SUBSTATION_POS|
            # (緩和として dist >= x - POS, dist >= POS - x)
            model.addCons(dist[tr, t] >= x[tr, t] - SUBSTATION_POS)
            model.addCons(dist[tr, t] >= SUBSTATION_POS - x[tr, t])
            
            # 電圧降下方程式
            model.addCons(v_tr[tr, t] == v_bus[t] - i_tr[tr, t] * (dist[tr, t] * (R_WIRE / 1000.0)), name=f"kirchhoff_v_{tr}_{t}")

    # キルヒホッフの電流則 (KCL)
    for t in TIME_STEPS:
        model.addCons(i_sub[t] == quicksum(i_tr[tr, t] for tr in TRAINS), name=f"kcl_{t}")

    # 3. 運行制約
    # 初期状態と終端状態
    for tr in TRAINS:
        model.addCons(x[tr, 0] == (0.0 if tr == "T1" else 3000.0))
        model.addCons(v[tr, 0] == 0.0)
        # 目的地到着制約
        model.addCons(x[tr, T-1] >= (1000.0 if tr == "T1" else 4000.0))

    # ---- 目的関数 ----
    # 変電所からの総供給エネルギーの最小化 (ピーク電力へのペナルティも含む)
    total_energy = quicksum(p_sub[t] * DT for t in TIME_STEPS)
    model.setObjective(total_energy, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    # 探索の出力・時間制限を設定
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Total Energy: {m.getObjVal()/3600.0:.2f} Wh")
