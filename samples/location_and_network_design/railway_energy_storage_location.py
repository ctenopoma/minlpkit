"""鉄道における地上蓄電設備(WESS) 最適配置・サイジングモデル (MILP)

列車の回生ブレーキによって発生する電力が、他の力行中の列車によって
消費しきれない場合「回生失効（電圧上昇によるブレーキ絞り込み）」が発生し、
エネルギーの無駄となります。
この回生余剰電力を吸収し、後に再利用するための「地上蓄電設備 (Wayside Energy Storage System)」を
沿線のどの変電所または駅に配置し、容量をいくらにするかを決定する最適化モデルです。
配置・容量コストと、回生失効の削減（省エネ効果）のトレードオフを評価します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Railway_Energy_Storage_Location")

    # ---- データ設定 ----
    # 候補地 (変電所 S1, S2, S3)
    CANDIDATES = ["S1", "S2", "S3"]
    
    # 時間断面 (T=10)
    T = 10
    TIME_STEPS = list(range(T))

    # 各候補地における各時刻の「回生余剰電力 (負の値が余剰)」または「力行不足電力 (正の値)」
    # 実際には潮流計算から得られるプロファイルを用いるが、ここでは固定シナリオとする
    # 正: そのノードで電力が欲しい (蓄電から放電可能)
    # 負: そのノードで電力が余っている (蓄電へ充電可能)
    NET_POWER = {
        "S1": [100, 200, -300, -100, 50,  150, 0,  -200, 100, 50],
        "S2": [50,  -100, -200, 300, 200, -50, -150, 100, 50, -50],
        "S3": [-200, 50,  100,  150, -100, 0,  200,  -50, -150, 100]
    }

    # 蓄電設備パラメータ
    FIXED_COST = 500.0   # 設置基本コスト [k$]
    CAP_COST = 2.0       # 容量比例コスト [k$/kWh]
    MAX_CAP = 500.0      # 最大容量 [kWh]
    
    # 充放電の最大レート (容量に対するCレート)
    C_RATE = 2.0
    EFF_CHG = 0.95
    EFF_DIS = 0.95

    # 余剰電力を捨てる（回生失効）コスト
    # ここでは、系統からの買電コストとみなす（捨てた分だけ後で買電が必要になるため）
    ELEC_PRICE = 0.15  # [k$/kWh] (シミュレーション上の重み)

    # ---- 変数定義 ----
    # 配置・容量変数
    # y[c]: 設置フラグ
    y = {c: model.addVar(vtype="B", name=f"y_{c}") for c in CANDIDATES}
    # cap[c]: 設置容量 [kWh]
    cap = {c: model.addVar(vtype="C", lb=0.0, ub=MAX_CAP, name=f"cap_{c}") for c in CANDIDATES}

    # 運用変数
    # soc[c, t]: 蓄電設備のSOC [kWh]
    soc = {}
    # p_chg[c, t]: 蓄電池への充電電力 [kW] (NET_POWERが負のときに吸収)
    p_chg = {}
    # p_dis[c, t]: 蓄電池からの放電電力 [kW] (NET_POWERが正のときに供給)
    p_dis = {}
    # p_grid[c, t]: 系統から買う電力 (不足分)
    p_grid = {}
    # p_loss[c, t]: 回生失効で捨てる電力 (余剰分)
    p_loss = {}

    for c in CANDIDATES:
        for t in range(T + 1):
            soc[c, t] = model.addVar(vtype="C", lb=0.0, ub=MAX_CAP, name=f"soc_{c}_{t}")
        for t in TIME_STEPS:
            p_chg[c, t] = model.addVar(vtype="C", lb=0.0, name=f"p_chg_{c}_{t}")
            p_dis[c, t] = model.addVar(vtype="C", lb=0.0, name=f"p_dis_{c}_{t}")
            p_grid[c, t] = model.addVar(vtype="C", lb=0.0, name=f"p_grid_{c}_{t}")
            p_loss[c, t] = model.addVar(vtype="C", lb=0.0, name=f"p_loss_{c}_{t}")

    # ---- 制約定義 ----
    for c in CANDIDATES:
        # 容量とバイナリの連動
        model.addCons(cap[c] <= MAX_CAP * y[c])

        # 初期SOC
        model.addCons(soc[c, 0] == 0.0)

        for t in TIME_STEPS:
            # SOCの制限 (容量以下)
            model.addCons(soc[c, t] <= cap[c])
            model.addCons(soc[c, t+1] <= cap[c])

            # 充放電レート制約
            model.addCons(p_chg[c, t] <= C_RATE * cap[c])
            model.addCons(p_dis[c, t] <= C_RATE * cap[c])

            # SOCダイナミクス (dt=1時間とする)
            model.addCons(soc[c, t+1] == soc[c, t] + p_chg[c, t] * EFF_CHG - p_dis[c, t] / EFF_DIS)

            # ノード電力バランス
            # 必要な電力(正) or 余剰(負) + 充電(正) - 放電(負) = 系統買電(正) - 失効(負)
            # NET_POWER[c][t] + p_chg - p_dis == p_grid - p_loss
            model.addCons(NET_POWER[c][t] + p_chg[c, t] - p_dis[c, t] == p_grid[c, t] - p_loss[c, t])

    # ---- 目的関数 ----
    # 設備コスト (年化等価コストへの換算係数を掛けるイメージ、ここでは簡略化)
    # + 系統買電コストの合計を最小化
    obj = quicksum(FIXED_COST * y[c] + CAP_COST * cap[c] for c in CANDIDATES) \
          + quicksum(p_grid[c, t] * ELEC_PRICE for c in CANDIDATES for t in TIME_STEPS)
          
    model.setObjective(obj, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Location Cost: {m.getObjVal():.2f}")
        for c in CANDIDATES:
            val = m.getVal(m.getVars()[m.getVars().index([v for v in m.getVars() if v.name == f"y_{c}"][0])])
            if val > 0.5:
                print(f"Install WESS at {c}")
