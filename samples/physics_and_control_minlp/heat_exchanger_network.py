"""熱交換ネットワーク合成問題 (Heat Exchanger Network Synthesis - HENS)

化学プロセス設計において、エネルギー消費量（外部ユーティリティ使用量）と
熱交換器の設備投資コスト（固定費および伝熱面積比例費）の合計を最小化する問題です。
高温流体から低温流体への熱回収量、必要面積の算出（温度差と熱量の関係）、
および熱交換器を設置するか否か（バイナリ変数）を決定します。
「伝熱面積 × 平均温度差 ＝ 熱量 / 総括伝熱係数」という関係から双線形項（Bilinear term）が生じ、
さらに設備投資にバイナリ変数を伴うため、典型的な非凸混合整数非線形計画法 (MINLP) となります。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Heat_Exchanger_Network_Synthesis")

    # ---- データ設定 ----
    # 高温流体 (H1, H2): 入口温度[K], 出口温度[K], 熱容量流量[kW/K]
    HOT = {
        "H1": {"Tin": 400.0, "Tout": 340.0, "F": 2.0},  # 熱量 = 2 * (400 - 340) = 120 kW
        "H2": {"Tin": 420.0, "Tout": 360.0, "F": 1.5},  # 熱量 = 1.5 * (420 - 360) = 90 kW
    }

    # 低温流体 (C1, C2): 入口温度[K], 出口温度[K], 熱容量流量[kW/K]
    COLD = {
        "C1": {"Tin": 300.0, "Tout": 390.0, "f": 1.8},  # 熱量 = 1.8 * (390 - 300) = 162 kW
        "C2": {"Tin": 320.0, "Tout": 380.0, "f": 1.2},  # 熱量 = 1.2 * (380 - 320) = 72 kW
    }

    # ユーティリティコスト: 冷却ユーティリティ [$/kW], 加熱ユーティリティ [$/kW]
    C_CU = 10.0
    C_HU = 80.0

    # 熱交換器コストパラメータ: 固定費 [$], 面積単価 [$/m^2]
    C_FIXED = 1000.0
    C_AREA = 200.0

    # 総括伝熱係数 [kW/(m^2 K)]
    U = 0.5

    # 最小アプローチ温度差 [K] (熱交換器内の局所温度差の下限)
    DT_MIN = 10.0

    # 許容される熱量の最大値 (Big-Mとしても使用)
    Q_MAX = 200.0
    BIG_M = 500.0

    # ---- 変数定義 ----
    # z[i, j]: 高温流体 i と低温流体 j の間に熱交換器を設置するとき1 (バイナリ)
    z = {}
    # q[i, j]: 熱交換器 (i,j) で交換される熱量 [kW] (連続)
    q = {}
    # A[i, j]: 熱交換器 (i,j) の伝熱面積 [m^2] (連続)
    A = {}
    # dt1[i, j], dt2[i, j]: 熱交換器の両端での温度差 [K] (連続)
    dt1 = {}
    dt2 = {}
    for i in HOT:
        for j in COLD:
            z[i, j] = model.addVar(vtype="B", name=f"z_{i}_{j}")
            q[i, j] = model.addVar(vtype="C", lb=0.0, ub=Q_MAX, name=f"q_{i}_{j}")
            A[i, j] = model.addVar(vtype="C", lb=0.0, name=f"A_{i}_{j}")
            dt1[i, j] = model.addVar(vtype="C", lb=DT_MIN, ub=BIG_M, name=f"dt1_{i}_{j}")
            dt2[i, j] = model.addVar(vtype="C", lb=DT_MIN, ub=BIG_M, name=f"dt2_{i}_{j}")

    # q_cu[i]: 高温流体 i を冷却するためのユーティリティ（冷却器）の熱量 [kW] (連続)
    q_cu = {}
    for i in HOT:
        q_cu[i] = model.addVar(vtype="C", lb=0.0, name=f"q_cu_{i}")

    # q_hu[j]: 低温流体 j を加熱するためのユーティリティ（加熱器）の熱量 [kW] (連続)
    q_hu = {}
    for j in COLD:
        q_hu[j] = model.addVar(vtype="C", lb=0.0, name=f"q_hu_{j}")

    # ---- 制約定義 ----
    # 1. 各流体の総熱量バランス
    for i, hd in HOT.items():
        total_heat_needed = hd["F"] * (hd["Tin"] - hd["Tout"])
        model.addCons(
            quicksum(q[i, j] for j in COLD) + q_cu[i] == total_heat_needed,
            name=f"heat_balance_hot_{i}"
        )

    for j, cd in COLD.items():
        total_heat_needed = cd["f"] * (cd["Tout"] - cd["Tin"])
        model.addCons(
            quicksum(q[i, j] for i in HOT) + q_hu[j] == total_heat_needed,
            name=f"heat_balance_cold_{j}"
        )

    # 2. 熱量とバイナリの紐付け (設置しない場合は熱交換量は 0)
    for i in HOT:
        for j in COLD:
            model.addCons(
                q[i, j] <= Q_MAX * z[i, j],
                name=f"link_q_z_{i}_{j}"
            )

    # 3. 簡易ステージモデル（流体の入出口温度の近似）
    # HENSの厳密な温度バランスは非常に複雑なため、ここでは以下のシンプルなアプローチ温度差制約を用います。
    # 各熱交換器 (i,j) が設置された場合、その両端の温度差 dt1, dt2 は以下の関係を満たす必要があります。
    # dt1[i,j] = H1の入口温度 - C1の出口温度 (設置された場合)
    # dt2[i,j] = H1の出口温度 - C1の入口温度 (設置された場合)
    # 設置されない場合は、制約を無効化 (Big-Mで緩和)
    for i, hd in HOT.items():
        for j, cd in COLD.items():
            model.addCons(
                dt1[i, j] <= (hd["Tin"] - cd["Tout"]) + BIG_M * (1 - z[i, j]),
                name=f"dt1_upper_{i}_{j}"
            )
            model.addCons(
                dt2[i, j] <= (hd["Tout"] - cd["Tin"]) + BIG_M * (1 - z[i, j]),
                name=f"dt2_upper_{i}_{j}"
            )

    # 4. 伝熱面積 A[i,j] の計算 (非線形制約)
    # 算術平均温度差 AMTD = (dt1 + dt2)/2 を対数平均温度差 LMTD の近似として使用します。
    # q[i,j] <= U * A[i,j] * AMTD  ==>  2 * q[i,j] <= U * A[i,j] * (dt1[i,j] + dt2[i,j])
    # 設置されている場合のみ面積を計算
    for i in HOT:
        for j in COLD:
            model.addCons(
                2.0 * q[i, j] <= U * A[i, j] * (dt1[i, j] + dt2[i, j]),
                name=f"area_calc_{i}_{j}"
            )
            # 設置されていないときは面積 0
            model.addCons(
                A[i, j] <= BIG_M * z[i, j],
                name=f"area_zero_{i}_{j}"
            )

    # ---- 目的関数 ----
    # 総コスト = ユーティリティコスト + 熱交換器の固定投資費 + 面積比例費
    cost_utility = quicksum(q_cu[i] * C_CU for i in HOT) + quicksum(q_hu[j] * C_HU for j in COLD)
    cost_investment = quicksum(z[i, j] * C_FIXED + A[i, j] * C_AREA for i in HOT for j in COLD)
    model.setObjective(cost_utility + cost_investment, "minimize")

    model.data = {"z": z, "q": q, "A": A, "q_cu": q_cu, "q_hu": q_hu, "dt1": dt1, "dt2": dt2}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Network Cost: {model.getObjVal():.2f} $")
        d = model.data

        print("\n--- Heat Exchanger Allocation & Areas ---")
        for i in ["H1", "H2"]:
            for j in ["C1", "C2"]:
                z_val = model.getVal(d["z"][i, j])
                if z_val > 0.5:
                    q_val = model.getVal(d["q"][i, j])
                    a_val = model.getVal(d["A"][i, j])
                    dt1_val = model.getVal(d["dt1"][i, j])
                    dt2_val = model.getVal(d["dt2"][i, j])
                    print(f"  Exchanger ({i} <-> {j}): Heat = {q_val:5.1f} kW, Area = {a_val:5.1f} m^2 (dt1={dt1_val:.1f}K, dt2={dt2_val:.1f}K)")

        print("\n--- Utility Consumption ---")
        for i in ["H1", "H2"]:
            q_cu_val = model.getVal(d["q_cu"][i])
            print(f"  Cooler for {i}: {q_cu_val:.1f} kW")
        for j in ["C1", "C2"]:
            q_hu_val = model.getVal(d["q_hu"][j])
            print(f"  Heater for {j}: {q_hu_val:.1f} kW")

if __name__ == "__main__":
    main()
