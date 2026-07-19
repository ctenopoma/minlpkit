"""直流電気鉄道の変電所間協調電圧制御 (Substation Cooperative Control) MINLP

通常、直流変電所(TSS)は固定の無負荷送り出し電圧（例: 1500V）で運転されますが、
このモデルでは、路線上の各変電所がリアルタイムに通信し、
出力電圧を動的に上下させる「協調制御」を最適化します。
回生ブレーキを作動させている列車がいる場合、その付近の変電所電圧を意図的に下げることで、
回生電力を遠くの力行列車へ流れやすくし、回生失効（絞り込み）を防ぎます。
ただし、変電所間に過大な横流（クロス電流）が流れないよう、電圧差に制約を設けます。
非線形回路方程式（P = V * I）を完全に組み込んだ制御最適化モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Railway_Substation_Coordination_MINLP")

    # ---- データ設定 ----
    # 3つの変電所 (0km, 10km, 20km)
    SUBSTATIONS = {
        "S1": 0.0,
        "S2": 10.0,
        "S3": 20.0
    }
    
    # スナップショット (ある瞬間の列車の状態)
    # 列車: (位置[km], 消費電力[kW]) 負は回生電力
    # T1は力行中、T2は回生ブレーキ中、T3は力行中
    TRAINS = {
        "T1": (3.0,  2000.0),   # S1寄りで大量消費
        "T2": (12.0, -1500.0),  # S2付近で回生発電
        "T3": (18.0, 1000.0)    # S3寄りで消費
    }
    
    # 物理パラメータ
    V_NOMINAL = 1500.0
    V_MIN = 1400.0   # 制御下限電圧 [V]
    V_MAX = 1600.0   # 制御上限電圧 [V]
    
    R_WIRE = 0.03    # 架線・レール合成抵抗 [Ohm/km]
    
    # 横流(変電所間電流)の許容上限 [A]
    MAX_CROSS_CURRENT = 500.0

    # ノード集合 (変電所 + 列車)
    NODES = list(SUBSTATIONS.keys()) + list(TRAINS.keys())
    
    # ノードの位置を辞書化
    POS = {n: SUBSTATIONS[n] for n in SUBSTATIONS}
    POS.update({n: TRAINS[n][0] for n in TRAINS})
    
    # 位置順にノードをソートし、隣接するエッジを構成
    sorted_nodes = sorted(NODES, key=lambda n: POS[n])
    EDGES = []
    for i in range(len(sorted_nodes) - 1):
        EDGES.append((sorted_nodes[i], sorted_nodes[i+1]))
        
    # エッジの抵抗 [Ohm]
    R_EDGE = { (u, v): abs(POS[u] - POS[v]) * R_WIRE for u, v in EDGES }

    # ---- 変数定義 ----
    # v_node[n]: ノード n の電圧 [V]
    v_node = {}
    for n in NODES:
        if n in SUBSTATIONS:
            # 変電所の電圧は制御変数
            v_node[n] = model.addVar(vtype="C", lb=V_MIN, ub=V_MAX, name=f"v_{n}")
        else:
            # 列車のパンタグラフ電圧 (広い範囲を許容)
            v_node[n] = model.addVar(vtype="C", lb=900.0, ub=1800.0, name=f"v_{n}")

    # i_edge[u, v]: エッジ (u, v) を流れる電流 [A]
    i_edge = {}
    for (u, v) in EDGES:
        i_edge[u, v] = model.addVar(vtype="C", lb=-10000.0, ub=10000.0, name=f"i_{u}_{v}")

    # 変電所の供給電力 [kW] と 供給電流 [A]
    p_sub = {}
    i_sub = {}
    for s in SUBSTATIONS:
        # 変電所は整流器を想定し、逆流(系統への回生電力返還)はできない
        p_sub[s] = model.addVar(vtype="C", lb=0.0, name=f"p_sub_{s}")
        i_sub[s] = model.addVar(vtype="C", lb=0.0, name=f"i_sub_{s}")

    # 列車の消費電流 [A]
    i_tr = {}
    for tr in TRAINS:
        i_tr[tr] = model.addVar(vtype="C", lb=-5000.0, ub=5000.0, name=f"i_tr_{tr}")

    # ---- 制約定義 ----
    # 1. オームの法則 (枝の電圧降下)
    # V_u - V_v = R_uv * I_uv
    for (u, v) in EDGES:
        model.addCons(v_node[u] - v_node[v] == R_EDGE[u, v] * i_edge[u, v], name=f"ohm_{u}_{v}")

    # 2. キルヒホッフの電流則 (KCL)
    # ノード n において: Σ 流入 = Σ 流出
    for n in NODES:
        in_current = quicksum(i_edge[u, v] for u, v in EDGES if v == n)
        out_current = quicksum(i_edge[u, v] for u, v in EDGES if u == n)
        
        if n in SUBSTATIONS:
            # 変電所からの注入電流 i_sub
            model.addCons(in_current + i_sub[n] == out_current, name=f"kcl_{n}")
        else:
            # 列車の引き込み電流 i_tr (消費なら正)
            model.addCons(in_current == out_current + i_tr[n], name=f"kcl_{n}")

    # 3. 電力方程式 (非線形)
    # 変電所: P_sub [kW] = V * I / 1000
    for s in SUBSTATIONS:
        model.addCons(p_sub[s] * 1000.0 == v_node[s] * i_sub[s], name=f"p_sub_eq_{s}")

    # 列車: P_tr [kW] = V * I / 1000
    for tr in TRAINS:
        p_req = TRAINS[tr][1]
        model.addCons(p_req * 1000.0 == v_node[tr] * i_tr[tr], name=f"p_tr_eq_{tr}")

    # 4. 運用制約 (横流防止)
    # 簡易的に、隣接する変電所間の電圧差を小さくする
    # 厳密には、列車がいない状態での変電所間のループ電流を計算するべきだが、
    # ここでは単純に |V_s1 - V_s2| / R_cable <= MAX_CROSS_CURRENT
    for s1, s2 in [("S1", "S2"), ("S2", "S3")]:
        r_total = abs(SUBSTATIONS[s1] - SUBSTATIONS[s2]) * R_WIRE
        max_v_diff = MAX_CROSS_CURRENT * r_total
        model.addCons(v_node[s1] - v_node[s2] <= max_v_diff, name=f"cross_cur_upper_{s1}_{s2}")
        model.addCons(v_node[s2] - v_node[s1] <= max_v_diff, name=f"cross_cur_lower_{s1}_{s2}")

    # ---- 目的関数 ----
    # 全変電所からの総供給電力の最小化 (回生電力を最大限活用し、変電所からの持ち出しを減らす)
    # さらに、電圧を不必要に上げないための微小なペナルティを追加
    total_power = quicksum(p_sub[s] for s in SUBSTATIONS)
    voltage_penalty = quicksum((v_node[s] - V_MIN) * 0.001 for s in SUBSTATIONS)
    
    model.setObjective(total_power + voltage_penalty, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Total Power Supplied: {m.getObjVal():.2f} kW")
        # 制御された各変電所の電圧を表示
        for s in ["S1", "S2", "S3"]:
            v_val = m.getVal(m.getVars()[m.getVars().index([v for v in m.getVars() if v.name == f"v_{s}"][0])])
            print(f"Substation {s} Controlled Voltage: {v_val:.2f} V")
