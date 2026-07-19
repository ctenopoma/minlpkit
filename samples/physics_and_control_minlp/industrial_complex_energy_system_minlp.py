"""大規模複合施設向け 統合エネルギーシステム最適化 (MINLP)

大量の電力と冷温熱を消費する大規模施設（工場や大型商業施設）を対象に、
ガスタービン・コージェネレーション(CGS)、電動ヒートポンプ(EHP)、吸収式冷凍機、
蓄電池、および蓄熱槽を最適に運用する24時間スケジューリングモデルです。

本モデルは、外気温度(T_amb)の次元を組み込んでおり、以下の非線形・複雑な特性を考慮します：
1. ガスタービンの最大出力と効率（部分負荷効率曲線）の外気温度依存性（気温が高いと空気密度が低下し性能悪化）。
2. 電動ヒートポンプ(EHP)の成績係数(COP)の外気温度依存性。
3. 蓄熱槽からの自己放熱（外気温との温度差に比例）。
4. 時間帯別の電力料金（TOU）と太陽光発電(PV)の出力変動。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Industrial_Complex_Energy_System")

    # ---- データ設定 (24時間) ----
    T = 24
    TIME_STEPS = list(range(T))

    # 外気温度 [℃] (夏場を想定: 昼間は35℃まで上がる)
    T_AMB = [25.0, 24.5, 24.0, 23.5, 24.0, 25.0, 27.0, 29.0, 31.0, 33.0, 
             34.0, 35.0, 35.0, 34.5, 33.0, 31.0, 29.0, 27.0, 26.0, 25.5, 
             25.0, 25.0, 24.5, 25.0]

    # 需要データ [kW]
    DEMAND_ELEC = [500 + 100 * (t % 12) for t in TIME_STEPS]
    DEMAND_COOL = [200 + 300 * max(0, T_AMB[t] - 25) for t in TIME_STEPS]
    DEMAND_HEAT = [100 for t in TIME_STEPS]  # 給湯・プロセス熱などで一定と仮定

    # 太陽光発電(PV) 予測出力 [kW]
    PV_GEN = [0 if t < 6 or t > 18 else 200 * (1 - ((t - 12) / 6.0)**2) for t in TIME_STEPS]

    # 電力料金 [$/kWh] (昼間高く、夜間安い)
    PRICE_BUY = [10.0 if t < 8 or t >= 22 else 25.0 for t in TIME_STEPS]
    PRICE_SELL = [8.0 if t < 8 or t >= 22 else 15.0 for t in TIME_STEPS]
    PRICE_GAS = 12.0  # ガスコスト [$/kWh] (熱量換算)

    # 機器パラメータ
    GT_NOMINAL_CAP = 1000.0  # ISO条件(15℃)での定格出力
    # GT出力・効率の温度補正係数
    # 出力低下: P_max(T) = P_nom * (1 - 0.005 * (T - 15))
    # 燃料カーブ: Fuel = (a * P^2 + b * P + c) * (1 + 0.002 * (T - 15))  ※高温ほど燃費悪化
    GT_A, GT_B, GT_C = 0.0001, 2.0, 100.0

    # BESS (蓄電池)
    BATT_CAP = 1500.0
    BATT_CHG_MAX = 500.0
    BATT_EFF = 0.95

    # 蓄熱槽 (冷水)
    TES_CAP = 2000.0  # kWh_th
    TES_CHG_MAX = 800.0
    TES_LOSS_COEF = 0.05  # [kW/℃]

    # ---- 変数定義 ----
    # 系統電力
    p_buy = {t: model.addVar(vtype="C", lb=0.0, name=f"p_buy_{t}") for t in TIME_STEPS}
    p_sell = {t: model.addVar(vtype="C", lb=0.0, name=f"p_sell_{t}") for t in TIME_STEPS}

    # ガスタービン
    gt_on = {t: model.addVar(vtype="B", name=f"gt_on_{t}") for t in TIME_STEPS}
    p_gt = {t: model.addVar(vtype="C", lb=0.0, name=f"p_gt_{t}") for t in TIME_STEPS}
    fuel_gt = {t: model.addVar(vtype="C", lb=0.0, name=f"fuel_gt_{t}") for t in TIME_STEPS}
    q_gt_exh = {t: model.addVar(vtype="C", lb=0.0, name=f"q_gt_exh_{t}") for t in TIME_STEPS}

    # ヒートポンプ (EHP)
    p_ehp = {t: model.addVar(vtype="C", lb=0.0, name=f"p_ehp_{t}") for t in TIME_STEPS}
    q_ehp_cool = {t: model.addVar(vtype="C", lb=0.0, name=f"q_ehp_cool_{t}") for t in TIME_STEPS}

    # 吸収式冷凍機 (排熱利用)
    q_abs_in = {t: model.addVar(vtype="C", lb=0.0, name=f"q_abs_in_{t}") for t in TIME_STEPS}
    q_abs_cool = {t: model.addVar(vtype="C", lb=0.0, name=f"q_abs_cool_{t}") for t in TIME_STEPS}

    # 蓄電池 (BESS)
    soc_batt = {t: model.addVar(vtype="C", lb=0.0, ub=BATT_CAP, name=f"soc_batt_{t}") for t in TIME_STEPS}
    batt_chg = {t: model.addVar(vtype="C", lb=0.0, ub=BATT_CHG_MAX, name=f"batt_chg_{t}") for t in TIME_STEPS}
    batt_dis = {t: model.addVar(vtype="C", lb=0.0, ub=BATT_CHG_MAX, name=f"batt_dis_{t}") for t in TIME_STEPS}

    # 蓄熱槽 (TES)
    soc_tes = {t: model.addVar(vtype="C", lb=0.0, ub=TES_CAP, name=f"soc_tes_{t}") for t in TIME_STEPS}
    tes_chg = {t: model.addVar(vtype="C", lb=0.0, ub=TES_CHG_MAX, name=f"tes_chg_{t}") for t in TIME_STEPS}
    tes_dis = {t: model.addVar(vtype="C", lb=0.0, ub=TES_CHG_MAX, name=f"tes_dis_{t}") for t in TIME_STEPS}

    # ---- 制約定義 ----
    for t in TIME_STEPS:
        tamb = T_AMB[t]

        # 1. ガスタービンの外気温度特性 (非線形性)
        # 最大出力の低下
        p_gt_max_t = GT_NOMINAL_CAP * (1 - 0.005 * (tamb - 15.0))
        model.addCons(p_gt[t] <= p_gt_max_t * gt_on[t], name=f"gt_max_{t}")

        # 燃料消費特性 (部分負荷2次特性 ＋ 温度補正)
        temp_factor = 1.0 + 0.002 * (tamb - 15.0)
        # fuel = (A*p^2 + B*p + C*on) * temp_factor
        model.addCons(
            fuel_gt[t] == temp_factor * (GT_A * p_gt[t] * p_gt[t] + GT_B * p_gt[t] + GT_C * gt_on[t]),
            name=f"gt_fuel_{t}"
        )
        
        # 排熱発生量 (燃料の約50%が排熱として回収可能とする)
        model.addCons(q_gt_exh[t] == 0.5 * fuel_gt[t], name=f"gt_exh_{t}")

        # 2. ヒートポンプのCOP温度特性
        # 夏場の冷房COP: 外気温が高いほど下がる
        # COP = 6.0 - 0.1 * (T_amb - 25)
        cop_t = max(2.0, 6.0 - 0.1 * (tamb - 25.0))
        model.addCons(q_ehp_cool[t] == p_ehp[t] * cop_t, name=f"ehp_cop_{t}")

        # 3. 吸収式冷凍機
        # COP = 0.7 程度 (排熱から冷熱への変換)
        model.addCons(q_abs_cool[t] == q_abs_in[t] * 0.7, name=f"abs_cop_{t}")
        # 投入熱量はGT排熱の範囲内
        model.addCons(q_abs_in[t] <= q_gt_exh[t], name=f"abs_limit_{t}")

        # 4. バランス制約
        # 電力バランス
        # 需要 + 蓄電池充電 + EHP動力 == 系統買電 - 系統売電 + GT発電 + PV発電 + 蓄電池放電
        model.addCons(
            DEMAND_ELEC[t] + batt_chg[t] + p_ehp[t] == 
            p_buy[t] - p_sell[t] + p_gt[t] + PV_GEN[t] + batt_dis[t],
            name=f"elec_bal_{t}"
        )

        # 冷熱バランス
        # 需要 + 蓄熱充電 == EHP冷熱 + 吸収式冷熱 + 蓄熱放電
        model.addCons(
            DEMAND_COOL[t] + tes_chg[t] == 
            q_ehp_cool[t] + q_abs_cool[t] + tes_dis[t],
            name=f"cool_bal_{t}"
        )

        # 温熱バランス (GT排熱の残りを直接利用すると仮定)
        # 排熱 - 吸収式利用分 >= 温熱需要
        model.addCons(q_gt_exh[t] - q_abs_in[t] >= DEMAND_HEAT[t], name=f"heat_bal_{t}")

    # 5. 蓄エネルギーダイナミクス
    # T=0の初期状態
    model.addCons(soc_batt[0] == 500.0)
    model.addCons(soc_tes[0] == 500.0)
    
    for t in range(T - 1):
        # 蓄電池
        model.addCons(
            soc_batt[t+1] == soc_batt[t] + batt_chg[t] * BATT_EFF - batt_dis[t] / BATT_EFF,
            name=f"batt_dyn_{t}"
        )
        
        # 蓄熱槽 (放熱損失は外気温度との差に依存)
        # 簡易的に内部温度を5℃一定とし、外気との温度差による損失を計算
        loss_t = TES_LOSS_COEF * (T_AMB[t] - 5.0)
        # SOCが0に近い場合は損失ゼロにするための近似: 損失はSOCに比例させるなどするが、
        # ここではSOCが十分ある前提で固定量損失を引く（マイナス防止のため緩和）
        soc_next = soc_tes[t] + tes_chg[t] * 0.95 - tes_dis[t] / 0.95 - loss_t
        model.addCons(soc_tes[t+1] <= soc_next, name=f"tes_dyn_ub_{t}")
        # 非負制約は変数のlb=0で担保

    # 最終SOC制約 (24時間後に元に戻す)
    model.addCons(soc_batt[T-1] >= 500.0)
    model.addCons(soc_tes[T-1] >= 500.0)

    # ---- 目的関数 ----
    # 1日の総運用コスト最小化
    total_cost = quicksum(
        p_buy[t] * PRICE_BUY[t] 
        - p_sell[t] * PRICE_SELL[t] 
        + fuel_gt[t] * PRICE_GAS
        for t in TIME_STEPS
    )
    model.setObjective(total_cost, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    # 時間制限を設けて求解
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Daily Operation Cost: ${m.getObjVal():.2f}")
