"""電気自動車充電フリートスケジューリング (EV Charging Fleet Scheduling)

夜間に帰着する配送用の電気自動車 (EV) フリートを対象とし、翌朝の出発時間までに
必要なバッテリー充電量を確保しつつ、充電コスト（時間帯別電気料金）を最小化する問題です。
各車両の帰着・出発時刻、充電器（ポート）の同時接続数制限、
充電ポートごとの最大充電レート、および施設全体の受電上限電力を考慮した
混合整数線形計画法 (MILP) モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("EV_Charging_Fleet")

    # ---- データ設定 ----
    # タイムホライズン: 18:00 (t=0) から翌朝 08:00 (t=14) までの 14時間
    T = 14
    HOURS = list(range(T))
    
    # 時間帯別の電気料金 [円/kWh] (夜間の安さを反映)
    # 18:00 - 08:00 (t=0が18時, t=6が24時, t=13が朝7時)
    PRICE_ELEC = [
        18.0, 16.0, 14.0, 12.0, 10.0, 9.0,  # 18:00 - 23:59
        8.0,  8.0,  8.0,  9.0,  10.0, 12.0, # 00:00 - 05:59
        15.0, 18.0                          # 06:00 - 07:59
    ]

    # 充電器 (充電ポート): 最大出力 [kW]
    CHARGERS = {
        "Charger_1": 22.0,
        "Charger_2": 22.0,
        "Charger_3": 50.0,  # 急速充電器
    }

    # EV車両フリート: 帰着時刻ステップ, 出発時刻ステップ, 帰着時SOC[kWh], 目標SOC[kWh], バッテリー容量[kWh]
    VEHICLES = {
        "EV_A": {"t_arr": 0, "t_dep": 10, "soc_arr": 15.0, "soc_dep": 60.0, "capacity": 75.0}, # 18:00帰着 - 04:00出発
        "EV_B": {"t_arr": 2, "t_dep": 13, "soc_arr": 10.0, "soc_dep": 50.0, "capacity": 62.0}, # 20:00帰着 - 07:00出発
        "EV_C": {"t_arr": 4, "t_dep": 14, "soc_arr": 25.0, "soc_dep": 80.0, "capacity": 90.0}, # 22:00帰着 - 08:00出発
        "EV_D": {"t_arr": 1, "t_dep": 12, "soc_arr": 5.0,  "soc_dep": 55.0, "capacity": 60.0}, # 19:00帰着 - 06:00出発
    }

    # 施設全体の受電能力上限 [kW] (ピーク抑制)
    GRID_LIMIT = 80.0

    # 充電効率
    EFFICIENCY = 0.92

    # ---- 変数定義 ----
    # x[v, c, t]: 車両 v が時刻 t に充電器 c に接続されているとき 1 (バイナリ)
    x = {}
    # p[v, t]: 車両 v への時刻 t における実際の充電電力 [kW] (連続)
    p = {}
    for v in VEHICLES:
        for t in HOURS:
            p[v, t] = model.addVar(vtype="C", lb=0.0, name=f"p_{v}_{t}")
            for c in CHARGERS:
                x[v, c, t] = model.addVar(vtype="B", name=f"x_{v}_{c}_{t}")

    # soc[v, t]: 車両 v の時刻 t 終了時点における充電量 [kWh] (連続)
    soc = {}
    for v, vd in VEHICLES.items():
        for t in [-1] + HOURS:
            soc[v, t] = model.addVar(vtype="C", lb=0.0, ub=vd["capacity"], name=f"soc_{v}_{t}")

    # ---- 制約定義 ----
    for v, vd in VEHICLES.items():
        # 初期状態の設定 (帰着前の状態および帰着時のSOC)
        model.addCons(soc[v, -1] == vd["soc_arr"], name=f"init_soc_{v}")

        for t in HOURS:
            # 1. 帰着前および出発後は接続できない
            if t < vd["t_arr"] or t >= vd["t_dep"]:
                model.addCons(p[v, t] == 0.0, name=f"no_charge_outside_{v}_{t}")
                for c in CHARGERS:
                    model.addCons(x[v, c, t] == 0.0, name=f"no_connect_outside_{v}_{c}_{t}")

            # 2. 充電電力の上限は、接続されている充電器の最大出力によって決まる
            # p[v,t] <= sum( charger_limit * x[v,c,t] )
            model.addCons(
                p[v, t] <= quicksum(CHARGERS[c] * x[v, c, t] for c in CHARGERS),
                name=f"charge_power_limit_{v}_{t}"
            )

            # 3. 各車両 v は各時刻 t に高々1つの充電器にしか接続できない
            model.addCons(
                quicksum(x[v, c, t] for c in CHARGERS) <= 1,
                name=f"vehicle_port_excl_{v}_{t}"
            )

            # 4. バッテリーのSOCダイナミクス
            model.addCons(
                soc[v, t] == soc[v, t-1] + EFFICIENCY * p[v, t],
                name=f"soc_update_{v}_{t}"
            )

        # 5. 出発時刻における目標SOCの確保
        # 出発時刻の直前ステップ(t_dep - 1)での蓄電量が目標を上回る
        model.addCons(
            soc[v, vd["t_dep"] - 1] >= vd["soc_dep"],
            name=f"target_soc_{v}"
        )

    # 6. 充電器の同時接続数制限
    # 各充電器 c には各時刻 t に高々1台の車両しか接続できない
    for c in CHARGERS:
        for t in HOURS:
            model.addCons(
                quicksum(x[v, c, t] for v in VEHICLES) <= 1,
                name=f"charger_port_excl_{c}_{t}"
            )

    # 7. 施設全体のピーク制限 (契約電力上限)
    for t in HOURS:
        model.addCons(
            quicksum(p[v, t] for v in VEHICLES) <= GRID_LIMIT,
            name=f"facility_peak_limit_{t}"
        )

    # ---- 目的関数 ----
    # 総充電コストの最小化
    total_cost = quicksum(p[v, t] * PRICE_ELEC[t] for v in VEHICLES for t in HOURS)
    model.setObjective(total_cost, "minimize")

    model.data = {"x": x, "p": p, "soc": soc}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Total Charging Cost: {model.getObjVal():.2f} 円")
        d = model.data

        VEHICLES = ["EV_A", "EV_B", "EV_C", "EV_D"]
        CHARGERS = ["Charger_1", "Charger_2", "Charger_3"]

        print("\n--- Vehicle SOC and Charger Assignment ---")
        for v in VEHICLES:
            print(f"\n{v}:")
            for t in range(14):
                soc_val = model.getVal(d["soc"][v, t])
                p_val = model.getVal(d["p"][v, t])
                charger_used = None
                for c in CHARGERS:
                    if model.getVal(d["x"][v, c, t]) > 0.5:
                        charger_used = c
                        break
                
                status_str = f"Charging at {charger_used} ({p_val:.1f} kW)" if charger_used else "Parked / Charging Idle"
                print(f"  {t:02d}:00 | SOC: {soc_val:5.1f} kWh | {status_str}")

        print("\n--- Hourly Total Load vs Limit ---")
        for t in range(14):
            total_load = sum(model.getVal(d["p"][v, t]) for v in VEHICLES)
            print(f"  {t:02d}:00 | Total Load: {total_load:5.1f} kW / Limit: 80.0 kW")

if __name__ == "__main__":
    main()
