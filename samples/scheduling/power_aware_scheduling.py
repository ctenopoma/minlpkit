"""電力価格連動型の生産スケジューリング (Power-Aware Production Scheduling)

時間帯ごとに大きく変動する電力価格（リアルタイムプライシング）を考慮し、
電力多消費型産業（鉄鋼、セメント、化学など）における生産スケジュールを最適化します。
需要充足（必要な生産時間の確保）、各マシンの同時処理制約、
および契約電力枠（ピーク電力制限）のもとで、電力コストを最小化する混合整数線形計画法 (MILP) モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Power_Aware_Scheduling")

    # ---- データ設定 ----
    # タイムホライズン (24時間)
    T = 24
    HOURS = list(range(T))

    # 時間帯別の電力価格 [円/kWh] (昼間のピークや夜間の安さを模したパターン)
    POWER_PRICES = [
        12.0, 10.0, 10.0, 9.0,  9.0,  11.0, # 0:00 - 5:59
        15.0, 18.0, 22.0, 25.0, 28.0, 30.0, # 6:00 - 11:59 (昼のピーク)
        28.0, 26.0, 22.0, 20.0, 18.0, 17.0, # 12:00 - 17:59
        19.0, 22.0, 25.0, 20.0, 15.0, 13.0  # 18:00 - 23:59
    ]

    # マシン (生産ライン)
    MACHINES = ["Line1", "Line2", "Line3"]

    # ジョブ (製品)
    JOBS = {
        "Steel_A": {"duration": 8,  "power": 120.0},  # 必要生産時間 [h], 消費電力 [kW]
        "Steel_B": {"duration": 10, "power": 150.0},
        "Steel_C": {"duration": 6,  "power": 200.0},
        "Steel_D": {"duration": 12, "power": 80.0},
        "Steel_E": {"duration": 5,  "power": 250.0},
    }

    # ピーク電力制限 (契約電力制限) [kW]
    PEAK_POWER_LIMIT = 450.0

    # ---- 変数定義 ----
    # x[j, m, t]: 時刻tにマシンmでジョブjを処理しているとき1 (バイナリ)
    x = {}
    for j in JOBS:
        for m in MACHINES:
            for t in HOURS:
                x[j, m, t] = model.addVar(vtype="B", name=f"x_{j}_{m}_{t}")

    # p_total[t]: 時刻tにおける工場全体の総電力消費量 [kW] (連続)
    p_total = {}
    for t in HOURS:
        p_total[t] = model.addVar(vtype="C", lb=0.0, name=f"p_total_{t}")

    # ---- 制約定義 ----
    # 1. 各ジョブjは必要な時間数（duration）だけ処理される
    for j, jd in JOBS.items():
        model.addCons(
            quicksum(x[j, m, t] for m in MACHINES for t in HOURS) == jd["duration"],
            name=f"demand_satisfaction_{j}"
        )

    # 2. 各マシンmは各時刻tにおいて高々1つのジョブを処理できる
    for m in MACHINES:
        for t in HOURS:
            model.addCons(
                quicksum(x[j, m, t] for j in JOBS) <= 1,
                name=f"machine_capacity_{m}_{t}"
            )

    # 3. 総電力消費量の計算
    for t in HOURS:
        model.addCons(
            p_total[t] == quicksum(x[j, m, t] * jd["power"] for j, jd in JOBS.items() for m in MACHINES),
            name=f"power_calc_{t}"
        )

    # 4. ピーク電力制限 (契約電力)
    for t in HOURS:
        model.addCons(
            p_total[t] <= PEAK_POWER_LIMIT,
            name=f"peak_limit_{t}"
        )

    # 目的関数: 24時間の総電気代の最小化
    total_cost = quicksum(p_total[t] * POWER_PRICES[t] for t in HOURS)
    model.setObjective(total_cost, "minimize")

    model.data = {"x": x, "p_total": p_total}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Total Power Cost: {model.getObjVal():,.0f} 円")
        x = model.data["x"]
        p_total = model.data["p_total"]

        print("\n--- Hourly Power Consumption and Prices ---")
        JOBS = ["Steel_A", "Steel_B", "Steel_C", "Steel_D", "Steel_E"]
        MACHINES = ["Line1", "Line2", "Line3"]
        POWER_PRICES = [
            12.0, 10.0, 10.0, 9.0,  9.0,  11.0,
            15.0, 18.0, 22.0, 25.0, 28.0, 30.0,
            28.0, 26.0, 22.0, 20.0, 18.0, 17.0,
            19.0, 22.0, 25.0, 20.0, 15.0, 13.0
        ]
        
        print("Hour | Price (Yen/kWh) | Total Power (kW) | Schedule Detail")
        print("-----------------------------------------------------------")
        for t in range(24):
            pow_val = model.getVal(p_total[t])
            active = []
            for j in JOBS:
                for m in MACHINES:
                    if model.getVal(x[j, m, t]) > 0.5:
                        active.append(f"{j}({m})")
            detail = ", ".join(active) if active else "Idle"
            print(f"{t:4d} | {POWER_PRICES[t]:16.1f} | {pow_val:16.1f} | {detail}")

        max_peak = max(model.getVal(p_total[t]) for t in range(24))
        print(f"\nMax Peak Power Observed: {max_peak:.1f} kW (Limit: 450.0 kW)")

if __name__ == "__main__":
    main()
