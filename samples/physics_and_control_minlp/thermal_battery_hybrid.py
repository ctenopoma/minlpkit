"""蓄熱・蓄電ハイブリッドエネルギー管理システム (Thermal and Battery Hybrid EMS)

自家発電設備（熱電併給コジェネレーション: CHP）、蓄電池（BESS）、蓄熱槽（TES）、
および補助ボイラーを組み合わせた、工場・ビル向けのハイブリッドエネルギー管理システムです。
時間帯別の電力価格のもとで、電気需要と熱需要の両方を完全に満たしつつ、
システムの24時間分の運転コスト（燃料費＋電力網からの購入費）を最小化する混合整数線形計画法 (MILP) モデルです。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Thermal_Battery_Hybrid_EMS")

    # ---- データ設定 ----
    T = 24
    HOURS = list(range(T))

    # 電気需要 [kW] (昼間と夕方にピーク)
    DEMAND_ELEC = [
        30.0,  30.0,  30.0,  30.0,  30.0,  40.0,
        60.0,  80.0,  100.0, 110.0, 120.0, 120.0,
        110.0, 100.0, 90.0,  90.0,  100.0, 120.0,
        130.0, 110.0, 80.0,  60.0,  40.0,  30.0
    ]

    # 熱需要 [kW-thermal] (朝と夜にピーク)
    DEMAND_HEAT = [
        80.0,  80.0,  80.0,  90.0,  100.0, 120.0,
        110.0, 90.0,  70.0,  60.0,  50.0,  50.0,
        50.0,  60.0,  70.0,  80.0,  90.0,  100.0,
        110.0, 110.0, 100.0, 90.0,  80.0,  80.0
    ]

    # 電気料金 [円/kWh]
    PRICE_ELEC = [
        12.0, 10.0, 10.0, 9.0,  9.0,  11.0,
        15.0, 18.0, 22.0, 25.0, 28.0, 30.0,
        28.0, 26.0, 22.0, 20.0, 18.0, 17.0,
        19.0, 22.0, 25.0, 20.0, 15.0, 13.0
    ]

    # コジェネ (CHP): 発電容量 [kW], 熱電比, 燃料費単価 [円/kWh-input], 発電効率
    CHP = {
        "P_max": 80.0,
        "P_min": 20.0,
        "heat_power_ratio": 1.2,  # 発電量1kWに対し1.2kW-thermalの熱が発生
        "fuel_cost": 4.0,         # 燃料コスト単価
        "efficiency": 0.35,       # 発電効率
    }

    # ボイラー: 熱出力容量 [kW-thermal], 燃料費単価 [円/kWh-input], 効率
    BOILER = {
        "Q_max": 150.0,
        "fuel_cost": 4.0,
        "efficiency": 0.85,
    }

    # 蓄電池 (BESS): 容量 [kWh], 最大充放電 [kW], 充放電効率, 自己放電率
    BESS = {
        "capacity": 150.0,
        "power_max": 40.0,
        "eff": 0.90,
        "loss": 0.005,
    }

    # 蓄熱槽 (TES): 容量 [kWh-thermal], 最大充熱・放熱 [kW-thermal], 効率, 自己放熱率
    TES = {
        "capacity": 200.0,
        "power_max": 50.0,
        "eff": 0.95,
        "loss": 0.01,
    }

    # ---- 変数定義 ----
    # CHP運転変数: 発電量 p_chp, 運転フラグ u_chp (バイナリ)
    p_chp = {}
    u_chp = {}
    for t in HOURS:
        p_chp[t] = model.addVar(vtype="C", lb=0.0, ub=CHP["P_max"], name=f"p_chp_{t}")
        u_chp[t] = model.addVar(vtype="B", name=f"u_chp_{t}")

    # ボイラー熱出力
    q_boiler = {}
    for t in HOURS:
        q_boiler[t] = model.addVar(vtype="C", lb=0.0, ub=BOILER["Q_max"], name=f"q_boiler_{t}")

    # 買電量
    p_grid = {}
    for t in HOURS:
        p_grid[t] = model.addVar(vtype="C", lb=0.0, name=f"p_grid_{t}")

    # 蓄電池充放電・SOC
    c_bess = {}
    d_bess = {}
    soc_bess = {}
    for t in HOURS:
        c_bess[t] = model.addVar(vtype="C", lb=0.0, ub=BESS["power_max"], name=f"c_bess_{t}")
        d_bess[t] = model.addVar(vtype="C", lb=0.0, ub=BESS["power_max"], name=f"d_bess_{t}")
        soc_bess[t] = model.addVar(vtype="C", lb=0.1 * BESS["capacity"], ub=0.9 * BESS["capacity"], name=f"soc_bess_{t}")
    soc_bess[-1] = 0.5 * BESS["capacity"]  # 初期値

    # 蓄熱槽充放熱・SOC
    c_tes = {}
    d_tes = {}
    soc_tes = {}
    for t in HOURS:
        c_tes[t] = model.addVar(vtype="C", lb=0.0, ub=TES["power_max"], name=f"c_tes_{t}")
        d_tes[t] = model.addVar(vtype="C", lb=0.0, ub=TES["power_max"], name=f"d_tes_{t}")
        soc_tes[t] = model.addVar(vtype="C", lb=0.05 * TES["capacity"], ub=0.95 * TES["capacity"], name=f"soc_tes_{t}")
    soc_tes[-1] = 0.3 * TES["capacity"]  # 初期値

    # ---- 制約定義 ----
    for t in HOURS:
        # 1. CHPの発電容量上限・下限 (u_chpと紐付け)
        model.addCons(p_chp[t] >= CHP["P_min"] * u_chp[t], name=f"chp_min_{t}")
        model.addCons(p_chp[t] <= CHP["P_max"] * u_chp[t], name=f"chp_max_{t}")

        # 2. 電気需給バランス
        # CHP発電 + グリッド買電 + バッテリー放電 == 電気需要 + バッテリー充電
        model.addCons(
            p_chp[t] + p_grid[t] + d_bess[t] - c_bess[t] == DEMAND_ELEC[t],
            name=f"elec_balance_{t}"
        )

        # 3. 熱需給バランス
        # CHP発熱 + ボイラー熱出力 + 蓄熱槽放熱 == 熱需要 + 蓄熱槽充熱
        q_chp = p_chp[t] * CHP["heat_power_ratio"]
        model.addCons(
            q_chp + q_boiler[t] + d_tes[t] - c_tes[t] == DEMAND_HEAT[t],
            name=f"heat_balance_{t}"
        )

        # 4. 蓄電池の残量 (SOC) ダイナミクス
        model.addCons(
            soc_bess[t] == (1.0 - BESS["loss"]) * soc_bess[t-1] + BESS["eff"] * c_bess[t] - d_bess[t] / BESS["eff"],
            name=f"bess_soc_update_{t}"
        )

        # 5. 蓄熱槽の残量 (SOC) ダイナミクス
        model.addCons(
            soc_tes[t] == (1.0 - TES["loss"]) * soc_tes[t-1] + TES["eff"] * c_tes[t] - d_tes[t] / TES["eff"],
            name=f"tes_soc_update_{t}"
        )

    # タイムホライズン終了時のSOC復帰制約 (初期値と同等以上にすることで持続可能性を保証)
    model.addCons(soc_bess[T-1] >= 0.5 * BESS["capacity"], name="bess_soc_end")
    model.addCons(soc_tes[T-1] >= 0.3 * TES["capacity"], name="tes_soc_end")

    # ---- 目的関数 ----
    # コスト = 買電代 + CHP燃料費 + ボイラー燃料費
    # CHP燃料消費 = p_chp / CHP["efficiency"]
    # ボイラー燃料消費 = q_boiler / BOILER["efficiency"]
    cost_grid = quicksum(p_grid[t] * PRICE_ELEC[t] for t in HOURS)
    cost_chp = quicksum((p_chp[t] / CHP["efficiency"]) * CHP["fuel_cost"] for t in HOURS)
    cost_boiler = quicksum((q_boiler[t] / BOILER["efficiency"]) * BOILER["fuel_cost"] for t in HOURS)
    
    model.setObjective(cost_grid + cost_chp + cost_boiler, "minimize")

    model.data = {
        "p_chp": p_chp, "u_chp": u_chp, "q_boiler": q_boiler,
        "p_grid": p_grid, "c_bess": c_bess, "d_bess": d_bess, "soc_bess": soc_bess,
        "c_tes": c_tes, "d_tes": d_tes, "soc_tes": soc_tes
    }
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Operations Cost: {model.getObjVal():,.0f} 円")
        d = model.data

        # 24時間のエネルギーフローの詳細を表示
        print("\nHour | Grid(kW) | CHP(kW) | Boiler(kW) | BESS(SOC) | TES(SOC)")
        print("-----------------------------------------------------------------")
        for t in range(24):
            grid = model.getVal(d["p_grid"][t])
            chp = model.getVal(d["p_chp"][t])
            boiler = model.getVal(d["q_boiler"][t])
            bess_soc = model.getVal(d["soc_bess"][t])
            tes_soc = model.getVal(d["soc_tes"][t])
            print(f"{t:4d} | {grid:8.1f} | {chp:7.1f} | {boiler:10.1f} | {bess_soc:9.1f} | {tes_soc:8.1f}")

if __name__ == "__main__":
    main()
