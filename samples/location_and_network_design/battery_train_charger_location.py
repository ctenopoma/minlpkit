"""蓄電池列車(BEMU)のための駅急速充電設備 最適配置モデル (MILP)

非電化区間を運行する蓄電池搭載型列車(BEMU)において、
どの駅に急速充電設備を設置すべきかを決定する施設配置問題（Location-Routing/Scheduling拡張）です。
充電設備の設置コスト（バイナリ変数）と、
車両が各駅間を走行した際のバッテリーのState of Charge (SOC) ダイナミクスを連立し、
充電設備がない駅では充電できない制約下で、
SOCが下限を下回らない実行可能な運行を保証しつつ、総コストを最小化します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Battery_Train_Charger_Location")

    # ---- データ設定 ----
    STATIONS = [0, 1, 2, 3, 4]  # 5駅 (0から4へ往復などの運用を想定)
    
    # 候補地: 全ての駅に設置可能性があるが、両端は必須とする等の条件も可能
    CANDIDATES = STATIONS

    # コスト
    INSTALL_COST = 300.0  # 1駅あたりの充電器設置コスト
    
    # 車両バッテリー特性
    BATT_CAP = 150.0  # kWh
    MIN_SOC = 30.0    # kWh (劣化防止のための下限)
    INIT_SOC = 150.0

    # 運行スケジュール (片道3本、折り返し3本などを1日のシーケンスとする)
    # trips: (出発駅, 到着駅, 走行消費電力[kWh], 停車時間[分])
    TRIPS = [
        (0, 1, 20.0, 5.0),
        (1, 2, 35.0, 5.0),
        (2, 3, 25.0, 5.0),
        (3, 4, 30.0, 15.0), # 終点で長め停車
        (4, 3, 30.0, 5.0),
        (3, 2, 25.0, 5.0),
        (2, 1, 35.0, 5.0),
        (1, 0, 20.0, 30.0)
    ]
    N_TRIPS = len(TRIPS)

    # 充電性能
    CHG_RATE = 5.0  # kW/分 (停車1分あたり5kWh充電可能)

    # ---- 変数定義 ----
    # y[s]: 駅sに充電設備を設置するか (バイナリ)
    y = {s: model.addVar(vtype="B", name=f"y_{s}") for s in STATIONS}

    # soc[i]: トリップ i の「出発時」SOC
    soc = {i: model.addVar(vtype="C", lb=MIN_SOC, ub=BATT_CAP, name=f"soc_{i}") for i in range(N_TRIPS + 1)}
    
    # e_chg[i]: トリップ i 出発前の停車中に充電した電力量
    e_chg = {i: model.addVar(vtype="C", lb=0.0, name=f"e_chg_{i}") for i in range(N_TRIPS)}

    # ---- 制約定義 ----
    # 1. 初期SOC
    model.addCons(soc[0] == INIT_SOC)

    # 2. SOCダイナミクスと充電制限
    for i in range(N_TRIPS):
        dep, arr, energy, stop_time = TRIPS[i]
        
        # 前のトリップの到着駅から出発する際、その駅に充電設備があれば充電可能
        # 最大充電可能量 = CHG_RATE * stop_time
        max_charge = CHG_RATE * stop_time
        model.addCons(e_chg[i] <= max_charge * y[dep], name=f"max_chg_cap_{i}")
        
        # SOC更新 (次のトリップの出発時SOC)
        # = 現在のSOC + 充電量 - 走行消費
        model.addCons(soc[i] + e_chg[i] <= BATT_CAP, name=f"soc_upper_{i}")
        model.addCons(soc[i+1] == (soc[i] + e_chg[i]) - energy, name=f"soc_dyn_{i}")

    # 3. 必須設置条件など
    # 運用を回すため、少なくとも1箇所には置く
    model.addCons(quicksum(y[s] for s in STATIONS) >= 1)
    
    # 1日の終わりにSOCを一定以上残す
    model.addCons(soc[N_TRIPS] >= 100.0)

    # ---- 目的関数 ----
    # 充電設備の設置コストの最小化 (+ 劣化防止のためSOCの余裕も少し評価)
    obj = quicksum(INSTALL_COST * y[s] for s in STATIONS) - 0.1 * quicksum(soc[i] for i in range(N_TRIPS))
    model.setObjective(obj, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Location Cost: {m.getObjVal():.2f}")
        for s in STATIONS:
            val = m.getVal(m.getVars()[m.getVars().index([v for v in m.getVars() if v.name == f"y_{s}"][0])])
            if val > 0.5:
                print(f"Install Charger at Station {s}")
