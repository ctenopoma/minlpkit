"""蓄電池列車(BEMU)の運行ダイヤ・充電スケジュール統合最適化 (MILP)

電化区間と非電化区間が混在する路線において、蓄電池搭載型列車 (BEMU) の
運行ダイヤ（各駅の到着・出発時刻）と充電スケジュールを同時に最適化します。
電化区間走行中 (In-motion charging) および駅停車中 (Stationary charging) の
充電量を制御し、全区間でのSOC (State of Charge) を許容範囲内に保ちつつ、
バッテリー寿命への悪影響（深い放電のペナルティ）と、
運行ダイヤの基準からのズレ（遅延・早着）を最小化するモデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Battery_Train_Scheduling")

    # ---- データ設定 ----
    STATIONS = [0, 1, 2, 3]  # 4つの駅
    # 駅間の電化状態 (0->1: 電化, 1->2: 非電化, 2->3: 非電化)
    ELECTRIFIED_SECTION = {0: True, 1: False, 2: False}
    ELECTRIFIED_STATION = {0: True, 1: True, 2: False, 3: True}

    # 各駅間の基本走行時間と基準消費電力量
    RUN_TIME = {0: 10.0, 1: 15.0, 2: 12.0}     # 分
    BASE_ENERGY = {0: 50.0, 1: 70.0, 2: 60.0}  # kWh (力行消費 - 回生)

    # 基準となる計画ダイヤ (Planned Arrival/Departure)
    PLAN_A = {0: 0.0, 1: 12.0, 2: 30.0, 3: 45.0}
    PLAN_D = {0: 2.0, 1: 15.0, 2: 33.0, 3: 48.0}
    
    # 許容されるダイヤのズレ幅
    MAX_SHIFT = 5.0 # 分

    # バッテリーパラメータ
    BATT_CAP = 300.0  # 容量 [kWh]
    MAX_SOC = 270.0
    MIN_SOC = 60.0
    INIT_SOC = 250.0

    # 充電レートの上限 [kW]
    P_CHG_STAT = 600.0  # 停車中 (1分で10kWh)
    P_CHG_DYN = 300.0   # 走行中 (1分で5kWh)

    # ---- 変数定義 ----
    # a[s], d[s]: 駅sへの到着時刻、出発時刻 [分]
    a = {}
    d = {}
    for s in STATIONS:
        a[s] = model.addVar(vtype="C", lb=PLAN_A[s]-MAX_SHIFT, ub=PLAN_A[s]+MAX_SHIFT, name=f"a_{s}")
        d[s] = model.addVar(vtype="C", lb=PLAN_D[s]-MAX_SHIFT, ub=PLAN_D[s]+MAX_SHIFT, name=f"d_{s}")

    # e_stat[s], e_dyn[s]: 駅sでの停車中充電量[kWh]、駅s->s+1の走行中充電量[kWh]
    e_stat = {}
    e_dyn = {}
    for s in STATIONS:
        e_stat[s] = model.addVar(vtype="C", lb=0.0, name=f"e_stat_{s}")
    for s in STATIONS[:-1]:
        e_dyn[s] = model.addVar(vtype="C", lb=0.0, name=f"e_dyn_{s}")

    # soc[s]: 駅s到着時のSOC, soc_d[s]: 駅s出発時のSOC
    soc = {}
    soc_d = {}
    for s in STATIONS:
        soc[s] = model.addVar(vtype="C", lb=MIN_SOC, ub=MAX_SOC, name=f"soc_{s}")
        soc_d[s] = model.addVar(vtype="C", lb=MIN_SOC, ub=MAX_SOC, name=f"soc_d_{s}")

    # ダイヤからのズレ絶対値
    dev_a = {}
    dev_d = {}
    for s in STATIONS:
        dev_a[s] = model.addVar(vtype="C", lb=0.0)
        dev_d[s] = model.addVar(vtype="C", lb=0.0)
        model.addCons(dev_a[s] >= a[s] - PLAN_A[s])
        model.addCons(dev_a[s] >= PLAN_A[s] - a[s])
        model.addCons(dev_d[s] >= d[s] - PLAN_D[s])
        model.addCons(dev_d[s] >= PLAN_D[s] - d[s])

    # ---- 制約定義 ----
    # 1. 時間制約
    for s in STATIONS[:-1]:
        # 走行時間
        model.addCons(a[s+1] - d[s] >= RUN_TIME[s], name=f"run_time_{s}")
    for s in STATIONS:
        # 停車時間 (最小1分)
        if s > 0 and s < STATIONS[-1]:
            model.addCons(d[s] - a[s] >= 1.0, name=f"stop_time_{s}")
        elif s == 0:
            model.addCons(d[s] - a[s] >= 0.0)

    # 2. 充電量の上限 (充電時間に基づく)
    for s in STATIONS:
        if ELECTRIFIED_STATION[s]:
            # 停車中充電量 <= P_CHG_STAT * (d[s] - a[s]) / 60
            model.addCons(e_stat[s] <= (P_CHG_STAT / 60.0) * (d[s] - a[s]), name=f"max_e_stat_{s}")
        else:
            model.addCons(e_stat[s] == 0.0)
            
    for s in STATIONS[:-1]:
        if ELECTRIFIED_SECTION[s]:
            # 走行中充電量 <= P_CHG_DYN * (a[s+1] - d[s]) / 60
            model.addCons(e_dyn[s] <= (P_CHG_DYN / 60.0) * (a[s+1] - d[s]), name=f"max_e_dyn_{s}")
        else:
            model.addCons(e_dyn[s] == 0.0)

    # 3. SOCダイナミクス
    model.addCons(soc[0] == INIT_SOC)
    for s in STATIONS:
        # 出発時SOC = 到着時SOC + 停車中充電
        model.addCons(soc_d[s] == soc[s] + e_stat[s])
    for s in STATIONS[:-1]:
        # 次の駅の到着時SOC = 出発時SOC - 走行消費 + 走行中充電
        model.addCons(soc[s+1] == soc_d[s] - BASE_ENERGY[s] + e_dyn[s])

    # ---- 目的関数 ----
    # ダイヤのズレの最小化 + バッテリー劣化ペナルティ (低いSOCの回避 = 総充電量の最大化)
    # 簡易的に、充電設備の利用を最適化し、ズレを最小にする
    penalty = quicksum(dev_a[s] + dev_d[s] for s in STATIONS)
    # 終端でのSOCをできるだけ残す (放電深度を浅くする)
    obj = penalty * 100.0 - soc[STATIONS[-1]]
    model.setObjective(obj, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal objective: {m.getObjVal():.2f}")
