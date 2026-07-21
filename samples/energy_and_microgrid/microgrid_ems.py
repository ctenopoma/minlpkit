"""マイクログリッドEMS運用計画 (Microgrid Energy Management System, EMS)

事業ストーリー
--------------
離島や工場敷地内のマイクログリッド(ディーゼル発電機・太陽光・蓄電池を持つ小規模系統)を
運用するエネルギー管理担当者が、24時間分の需要予測と日射予測を踏まえて、各時間帯の
ディーゼル発電出力・蓄電池の充放電をどう配分すれば、燃料コストを最小化しつつ需要を
満たせるかを決める問題である。ディーゼル発電機は起動すると最低出力を維持しなければ
非効率になり(部分負荷での燃費悪化・機器摩耗)、蓄電池は充放電に上下限があり、
残量(SOC)は物理的な容量の範囲に収まらなければならない。日中は太陽光が需要の一部を
賄うが、夜間はディーゼルと蓄電池の放電に頼ることになるため、日中に蓄電池を充電して
夜間放電に備える「時間結合」の計画が燃料コスト最小化の鍵となる。

各制約の業務的意味:
- **需給バランス**: 各時間帯でディーゼル出力+太陽光+放電-充電が需要と一致しなければ
  ならない(発電と消費は瞬時に釣り合う必要がある電力系統の基本則)。
- **ディーゼル発電機の起動判断と最低出力**: 起動する時間帯は二値変数で表し、起動時は
  最低出力を下回れない(部分負荷運転を避けミスファイア・燃費悪化を防ぐ)。起動には
  スタートアップコストもかかる。
- **蓄電池のSOCダイナミクス**: 各時間帯末のSOCは前時間帯末のSOC+充電量-放電量で決まり、
  容量上限・下限(過放電による劣化防止)の範囲に収める。
- **充放電レート上限**: バッテリーのC-rate(充放電速度)による物理的な制約。

(元の学術的定式化: Parisio, A., Rikos, E., & Glielmo, L. (2014). A model predictive
control approach to microgrid operation optimization. IEEE Transactions on Control
Systems Technology, 22(5), 1813-1827.)
"""

from pyscipopt import Model, quicksum


def build_model(infeasible=False):
    m = Model("Microgrid_EMS")

    # ---- データ設定: 24時間、1時間刻み ----
    T = 24
    HOURS = list(range(T))

    # 需要予測 [kW] (昼と夕方にピークを持つ典型的な負荷パターン)
    demand = [
        40, 38, 36, 35, 36, 40,   # 00:00-05:59 深夜帯
        50, 65, 78, 82, 85, 88,   # 06:00-11:59 朝〜昼にかけ増加
        90, 86, 80, 78, 82, 95,   # 12:00-17:59 昼〜夕方
        110, 105, 88, 70, 58, 46,  # 18:00-23:59 夕方ピーク後に減少
    ]

    # 太陽光発電予測 [kW] (日中のみ発電、天候変動を模した山型)
    solar_gen = [
        0, 0, 0, 0, 0, 2,
        8, 20, 35, 48, 58, 63,
        65, 60, 50, 36, 20, 6,
        0, 0, 0, 0, 0, 0,
    ]

    # ディーゼル発電機: 燃料費[円/kWh]、起動費[円]、出力上限[kW]、最低出力比率
    diesel_cost = 18.0
    diesel_startup_cost = 800.0
    diesel_max = 70.0
    diesel_min_ratio = 0.3  # 起動時は上限の30%を下回れない

    # 蓄電池: 容量[kWh]、充放電レート上限[kW]、初期SOC[kWh]、充放電効率
    battery_max_cap = 200.0
    battery_min_cap = 20.0  # 過放電防止の下限(容量の10%)
    battery_max_charge = 40.0
    battery_max_discharge = 40.0
    battery_init_soc = 100.0
    charge_eff = 0.95
    discharge_eff = 0.95

    if infeasible:
        diesel_max = 0.0
        battery_max_charge = 0.0
        battery_max_discharge = 0.0

    # ---- 変数定義 ----
    diesel = {}      # ディーゼル発電出力 [kW]
    diesel_on = {}   # ディーゼル起動状態 (0/1)
    diesel_start = {}  # 起動(前時間帯オフ→今オン)を捉える二値変数
    charge = {}       # 蓄電池充電量 [kW]
    discharge = {}    # 蓄電池放電量 [kW]
    soc = {}          # 蓄電池残量(State of Charge) [kWh]

    for t in HOURS:
        diesel[t] = m.addVar(vtype="C", lb=0, ub=diesel_max, name=f"diesel_{t}")
        diesel_on[t] = m.addVar(vtype="B", name=f"diesel_on_{t}")
        diesel_start[t] = m.addVar(vtype="B", name=f"diesel_start_{t}")
        charge[t] = m.addVar(vtype="C", lb=0, ub=battery_max_charge, name=f"charge_{t}")
        discharge[t] = m.addVar(vtype="C", lb=0, ub=battery_max_discharge, name=f"discharge_{t}")
        soc[t] = m.addVar(vtype="C", lb=battery_min_cap, ub=battery_max_cap, name=f"soc_{t}")

    # ---- 目的関数: 燃料コスト + 起動コストの最小化 ----
    m.setObjective(
        quicksum(diesel_cost * diesel[t] + diesel_startup_cost * diesel_start[t] for t in HOURS),
        "minimize",
    )

    # ---- 制約定義 ----
    for t in HOURS:
        # 需給バランス
        m.addCons(
            diesel[t] + solar_gen[t] + discharge[t] - charge[t] == demand[t],
            name=f"Power_Balance_{t}",
        )

        # ディーゼル発電機の起動判断と出力上限・最低出力
        m.addCons(diesel[t] <= diesel_max * diesel_on[t], name=f"Diesel_UB_{t}")
        m.addCons(diesel[t] >= diesel_min_ratio * diesel_max * diesel_on[t], name=f"Diesel_LB_{t}")

        # 起動検知: t時点でオン かつ (t=0またはt-1時点でオフ) なら start=1
        if t == 0:
            m.addCons(diesel_start[t] >= diesel_on[t], name=f"Diesel_Start_{t}")
        else:
            m.addCons(diesel_start[t] >= diesel_on[t] - diesel_on[t - 1], name=f"Diesel_Start_{t}")

        # 蓄電池のSOCダイナミクス(充放電効率を考慮)
        if t == 0:
            m.addCons(
                soc[t] == battery_init_soc + charge_eff * charge[t] - discharge[t] / discharge_eff,
                name=f"SOC_Dyn_{t}",
            )
        else:
            m.addCons(
                soc[t] == soc[t - 1] + charge_eff * charge[t] - discharge[t] / discharge_eff,
                name=f"SOC_Dyn_{t}",
            )

    # 最終時間帯のSOCは初期値以上に戻す(翌日の運用に備える循環条件)
    m.addCons(soc[T - 1] >= battery_init_soc, name="SOC_End_Recovery")

    return m


def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value:", m.getObjVal())
    else:
        print("Status:", m.getStatus())


if __name__ == "__main__":
    main()
