"""直流電気鉄道の変電所 最適配置・サイジング問題 (MINLP)

路線上の複数の候補地から、直流変電所（TSS: Traction Substation）を
どこに設置し、どの程度の容量を持たせるかを決定する施設配置問題です。
各時間断面における列車の位置と消費電力に基づく「潮流計算（架線電圧降下）」を組み込み、
全列車のパンタグラフ電圧が許容下限を下回らないようにしつつ、
変電所の建設コスト（初期費用＋容量比例費用）と運用時の電力損失の総和を最小化します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Railway_Substation_Location")

    # ---- データ設定 ----
    # 候補地 (キロ程 [km])
    CANDIDATES = [0.0, 5.0, 10.0, 15.0, 20.0]
    
    # 時刻断面と列車の位置・電力需要 (シミュレーションスナップショット)
    # 簡単のため3つのスナップショット(t)を考える
    # 各tにおける列車のリスト: (位置 [km], 消費電力 [kW]) 負は回生
    TRAIN_STATES = {
        0: [(2.0, 2000.0), (12.0, 1500.0)],
        1: [(5.0, 3000.0), (18.0, 2500.0)],
        2: [(8.0, -1000.0), (20.0, 3000.0)]
    }
    TIME_STEPS = list(TRAIN_STATES.keys())

    # 電気特性パラメータ
    V_NOMINAL = 1500.0   # 変電所の無負荷送り出し電圧 [V]
    V_MIN = 900.0        # パンタグラフ電圧の下限許容値 [V]
    V_MAX = 1800.0       # 回生時の上限電圧 [V]
    R_WIRE = 0.03        # 架線・レール合成抵抗 [Ohm/km]

    # コストパラメータ
    FIXED_COST = 500.0   # 変電所1か所あたりの基本建設費 [k$]
    CAP_COST = 0.1       # 容量比例コスト [k$/kW]
    MAX_CAP = 10000.0    # 1変電所の最大容量 [kW]

    # ---- 変数定義 ----
    # 配置・サイジング変数
    # y[c]: 候補地 c に変電所を設置するかどうか (バイナリ)
    y = {c: model.addVar(vtype="B", name=f"y_{c}") for c in CANDIDATES}
    # cap[c]: 候補地 c の変電所容量 [kW]
    cap = {c: model.addVar(vtype="C", lb=0.0, ub=MAX_CAP, name=f"cap_{c}") for c in CANDIDATES}

    # 運用変数 (各時刻スナップショット tごと)
    # v_bus[c, t]: 変電所 c のバス電圧 [V]
    # i_sub[c, t]: 変電所 c からの送り出し電流 [A]
    # p_sub[c, t]: 変電所 c の供給電力 [kW]
    v_bus = {}
    i_sub = {}
    p_sub = {}
    for t in TIME_STEPS:
        for c in CANDIDATES:
            v_bus[c, t] = model.addVar(vtype="C", lb=0.0, ub=V_NOMINAL, name=f"v_bus_{c}_{t}")
            # ダイオード整流器を想定し、逆流(回生電力の系統への返還)は不可とする
            i_sub[c, t] = model.addVar(vtype="C", lb=0.0, name=f"i_sub_{c}_{t}")
            p_sub[c, t] = model.addVar(vtype="C", lb=0.0, name=f"p_sub_{c}_{t}")

    # 列車変数
    # v_tr[t, i]: 時刻 t の列車 i の電圧 [V]
    # i_tr[t, i]: 時刻 t の列車 i の電流 [A]
    v_tr = {}
    i_tr = {}
    for t in TIME_STEPS:
        for idx, (pos, p_req) in enumerate(TRAIN_STATES[t]):
            v_tr[t, idx] = model.addVar(vtype="C", lb=V_MIN, ub=V_MAX, name=f"v_tr_{t}_{idx}")
            i_tr[t, idx] = model.addVar(vtype="C", lb=-5000.0, ub=5000.0, name=f"i_tr_{t}_{idx}")

    # ---- 制約定義 ----
    # 1. 配置と容量の制約
    for c in CANDIDATES:
        model.addCons(cap[c] <= MAX_CAP * y[c], name=f"cap_limit_{c}")

    for t in TIME_STEPS:
        for c in CANDIDATES:
            # 設置されていない変電所からは電流・電力を流せない
            model.addCons(i_sub[c, t] <= 10000.0 * y[c], name=f"i_sub_off_{c}_{t}")
            model.addCons(p_sub[c, t] <= cap[c], name=f"p_sub_cap_{c}_{t}")

            # 電力 = 電圧 * 電流 / 1000 [kW]
            model.addCons(p_sub[c, t] * 1000.0 == v_bus[c, t] * i_sub[c, t], name=f"p_v_i_sub_{c}_{t}")
            
            # 稼働中の変電所の電圧は V_NOMINAL (内部抵抗無視の理想電圧源とする)
            # 未設置の場合は0でもよい
            # V_NOMINAL - v_bus <= M * (1 - y)
            model.addCons(V_NOMINAL - v_bus[c, t] <= V_NOMINAL * (1 - y[c]))
            model.addCons(v_bus[c, t] <= V_NOMINAL * y[c])

        for idx, (pos, p_req) in enumerate(TRAIN_STATES[t]):
            # 列車の消費電力 = 電圧 * 電流
            model.addCons(p_req * 1000.0 == v_tr[t, idx] * i_tr[t, idx], name=f"p_v_i_tr_{t}_{idx}")

        # 2. キルヒホッフの法則に基づく回路方程式
        # KCL: 総供給電流 == 総消費電流
        model.addCons(
            quicksum(i_sub[c, t] for c in CANDIDATES) == quicksum(i_tr[t, idx] for idx in range(len(TRAIN_STATES[t]))),
            name=f"kcl_{t}"
        )

        # 電圧降下 (簡易放射状近似: 各列車は最も近い稼働中の変電所から主たる電力供給を受けるとする)
        # 厳密なメッシュ解析はG行列の逆行列計算が必要なため、各列車と候補地の間の経路抵抗による不等式制約とする
        for idx, (pos, p_req) in enumerate(TRAIN_STATES[t]):
            for c in CANDIDATES:
                # 距離に基づく抵抗
                r = abs(pos - c) * R_WIRE
                # 候補地 c が変電所として設置されている場合、
                # 列車の電圧は変電所電圧から (電流 * 抵抗) 降下したものに近い。
                # 複数変電所からの並列供給があるため、v_tr <= v_bus - i_tr*r は厳密には成立しないが、
                # 電圧低下の最悪評価として、少なくとも1つの稼働変電所との間で V_tr >= V_bus - I_total * R を満たすような制約を組む。
                # ここでは単純化として、全変電所と列車の間の電圧差を流れる電流経路 i_link[c, tr] で定義する。
                pass

    # より厳密なノード方程式 (KCL & KVL) を導入
    # i_link[c, t, idx]: 候補地 c から列車 idx へ流れる電流
    i_link = {}
    for t in TIME_STEPS:
        for c in CANDIDATES:
            for idx in range(len(TRAIN_STATES[t])):
                i_link[c, t, idx] = model.addVar(vtype="C", lb=-5000.0, ub=5000.0, name=f"ilink_{c}_{t}_{idx}")

        for c in CANDIDATES:
            model.addCons(i_sub[c, t] == quicksum(i_link[c, t, idx] for idx in range(len(TRAIN_STATES[t]))))
            
        for idx, (pos, p_req) in enumerate(TRAIN_STATES[t]):
            model.addCons(i_tr[t, idx] == quicksum(i_link[c, t, idx] for c in CANDIDATES))

            for c in CANDIDATES:
                r = abs(pos - c) * R_WIRE
                # 変電所cが稼働(y=1)のとき、オームの法則 V_sub - V_tr = R * I_link
                # 非稼働(y=0)のときは I_link = 0
                BIG_M = 2000.0
                model.addCons(v_bus[c, t] - v_tr[t, idx] - r * i_link[c, t, idx] <= BIG_M * (1 - y[c]))
                model.addCons(v_bus[c, t] - v_tr[t, idx] - r * i_link[c, t, idx] >= -BIG_M * (1 - y[c]))
                model.addCons(i_link[c, t, idx] <= 5000.0 * y[c])
                model.addCons(i_link[c, t, idx] >= -5000.0 * y[c])

    # 少なくとも1つは変電所を設置する
    model.addCons(quicksum(y[c] for c in CANDIDATES) >= 1)

    # ---- 目的関数 ----
    # 建設コスト + 運用電力の和
    # (ここでは運用コストを単にスナップショットの合計とする)
    obj = quicksum(FIXED_COST * y[c] + CAP_COST * cap[c] for c in CANDIDATES) \
          + quicksum(p_sub[c, t] for c in CANDIDATES for t in TIME_STEPS) * 0.1
    
    model.setObjective(obj, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Location Cost: {m.getObjVal():.2f}")
