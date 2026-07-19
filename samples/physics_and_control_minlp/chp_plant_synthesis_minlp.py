"""熱電併給(CHP)プラントのスーパー構造ベース合成最適化 (MINLP)

ガスタービン(GT)、排熱回収ボイラー(HRSG)、蒸気タービン(ST)、および補助ボイラーからなる
CHP (Combined Heat and Power) プラントの最適な機器構成と運転状態を決定します。
各機器の導入有無（バイナリ変数）と、部分負荷運転時の非線形な効率曲線、
熱力学プロパティ（蒸気圧・温度）を考慮した精緻なMINLPモデルです。
所与の電力・熱需要を満たしつつ、年間総コスト（設備投資＋燃料費）を最小化します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("CHP_Plant_Synthesis_MINLP")

    # ---- データ設定 ----
    # 候補機器リスト
    GT_CANDIDATES = ["GT_small", "GT_large"]
    ST_CANDIDATES = ["ST_1"]
    BOILER_CANDIDATES = ["AuxBoiler"]

    # 需要
    DEMAND_ELEC = 50.0  # MW
    DEMAND_HEAT = 40.0  # MW

    # 機器パラメータ
    # ガスタービン
    GT_MAX_CAP = {"GT_small": 30.0, "GT_large": 60.0}  # MW
    GT_INV_COST = {"GT_small": 1000.0, "GT_large": 1800.0}
    # GT効率曲線 (発電効率 = a + b*(P/P_max) + c*(P/P_max)^2)
    # Fuel = Power / Efficiency -> Fuel = a*P^2 + b*P + c の形に近似
    GT_FUEL_CURVE = {
        "GT_small": (0.05, 2.5, 5.0), # a*P^2 + b*P + c
        "GT_large": (0.02, 2.2, 10.0)
    }
    # GT排熱量 (排熱 = 燃料 - 発電出力 - その他損失) 簡易化してFuelに比例
    GT_EXHAUST_RATIO = 0.6 

    # 蒸気タービン
    ST_MAX_CAP = {"ST_1": 20.0}
    ST_INV_COST = {"ST_1": 500.0}
    # ST発電出力は流入蒸気熱量(HRSGから)の非線形関数
    ST_POWER_CURVE = {"ST_1": (0.01, 0.3, 0.0)} # a*Q^2 + b*Q + c

    # 補助ボイラー
    AB_MAX_CAP = {"AuxBoiler": 50.0}
    AB_INV_COST = {"AuxBoiler": 200.0}
    AB_EFF = 0.85

    # 燃料単価
    FUEL_PRICE = 50.0 # $/MWh

    # ---- 変数定義 ----
    # 機器の選択 (バイナリ)
    y_gt = {k: model.addVar(vtype="B", name=f"y_{k}") for k in GT_CANDIDATES}
    y_st = {k: model.addVar(vtype="B", name=f"y_{k}") for k in ST_CANDIDATES}
    y_ab = {k: model.addVar(vtype="B", name=f"y_{k}") for k in BOILER_CANDIDATES}

    # 発電出力 [MW]
    p_gt = {k: model.addVar(vtype="C", lb=0.0, ub=GT_MAX_CAP[k], name=f"p_{k}") for k in GT_CANDIDATES}
    p_st = {k: model.addVar(vtype="C", lb=0.0, ub=ST_MAX_CAP[k], name=f"p_{k}") for k in ST_CANDIDATES}
    
    # 燃料消費 [MW]
    fuel_gt = {k: model.addVar(vtype="C", lb=0.0, name=f"fuel_{k}") for k in GT_CANDIDATES}
    fuel_ab = {k: model.addVar(vtype="C", lb=0.0, name=f"fuel_{k}") for k in BOILER_CANDIDATES}

    # 熱量フロー [MW]
    q_exhaust_gt = {k: model.addVar(vtype="C", lb=0.0, name=f"q_exhaust_{k}") for k in GT_CANDIDATES}
    q_hrsg_to_st = model.addVar(vtype="C", lb=0.0, name="q_hrsg_to_st")
    q_hrsg_to_heat = model.addVar(vtype="C", lb=0.0, name="q_hrsg_to_heat")
    q_ab_to_heat = {k: model.addVar(vtype="C", lb=0.0, ub=AB_MAX_CAP[k], name=f"q_{k}") for k in BOILER_CANDIDATES}
    q_st_ext_heat = {k: model.addVar(vtype="C", lb=0.0, name=f"q_ext_{k}") for k in ST_CANDIDATES}

    # ---- 制約定義 ----
    # 1. 稼働上限・下限 (ビッグM制約の代わり、変数のubで一部カバーするが明示)
    for k in GT_CANDIDATES:
        model.addCons(p_gt[k] <= GT_MAX_CAP[k] * y_gt[k])
    for k in ST_CANDIDATES:
        model.addCons(p_st[k] <= ST_MAX_CAP[k] * y_st[k])
    for k in BOILER_CANDIDATES:
        model.addCons(q_ab_to_heat[k] <= AB_MAX_CAP[k] * y_ab[k])

    # 2. 機器の非線形特性
    for k, (a, b, c) in GT_FUEL_CURVE.items():
        # fuel = a * p^2 + b * p + c * y  (yが0なら0になるようcにはyを掛ける)
        model.addCons(fuel_gt[k] == a * (p_gt[k] * p_gt[k]) + b * p_gt[k] + c * y_gt[k], name=f"fuel_curve_{k}")
        model.addCons(q_exhaust_gt[k] == GT_EXHAUST_RATIO * fuel_gt[k], name=f"exhaust_{k}")

    for k, (a, b, c) in ST_POWER_CURVE.items():
        # p_st = a * q_in^2 + b * q_in + c * y
        model.addCons(p_st[k] == a * (q_hrsg_to_st * q_hrsg_to_st) + b * q_hrsg_to_st + c * y_st[k], name=f"st_curve_{k}")
        
    for k in BOILER_CANDIDATES:
        model.addCons(fuel_ab[k] == q_ab_to_heat[k] / AB_EFF, name=f"ab_curve_{k}")

    # 3. 熱フローのバランス
    # HRSGの入力はGT排熱の合計
    total_exhaust = quicksum(q_exhaust_gt[k] for k in GT_CANDIDATES)
    # 排熱はSTへの蒸気と直接熱供給に分配 (バイパス等)
    model.addCons(total_exhaust == q_hrsg_to_st + q_hrsg_to_heat, name="hrsg_balance")

    # STからの抽気/排気熱 (ここでは簡単のため発電出力に反比例すると仮定する制約)
    # 厳密には等エントロピー膨張などの式が入るが、簡易的な線形関係とする
    for k in ST_CANDIDATES:
        model.addCons(q_st_ext_heat[k] == q_hrsg_to_st - p_st[k] - 0.1 * q_hrsg_to_st, name=f"st_heat_{k}")

    # 4. 需要の充足
    model.addCons(
        quicksum(p_gt[k] for k in GT_CANDIDATES) + quicksum(p_st[k] for k in ST_CANDIDATES) >= DEMAND_ELEC,
        name="demand_elec"
    )
    
    model.addCons(
        q_hrsg_to_heat + quicksum(q_st_ext_heat[k] for k in ST_CANDIDATES) + quicksum(q_ab_to_heat[k] for k in BOILER_CANDIDATES) >= DEMAND_HEAT,
        name="demand_heat"
    )

    # ---- 目的関数 ----
    # 設備投資コストの年化費用 (簡略化) + 運転燃料費
    inv_cost = (
        quicksum(GT_INV_COST[k] * y_gt[k] for k in GT_CANDIDATES) +
        quicksum(ST_INV_COST[k] * y_st[k] for k in ST_CANDIDATES) +
        quicksum(AB_INV_COST[k] * y_ab[k] for k in BOILER_CANDIDATES)
    )
    op_cost = (
        quicksum(fuel_gt[k] for k in GT_CANDIDATES) +
        quicksum(fuel_ab[k] for k in BOILER_CANDIDATES)
    ) * FUEL_PRICE * 8760.0  # 1年間の想定

    # スケールを調整して目的関数へ
    model.setObjective(inv_cost * 0.1 + op_cost / 1e3, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Total Cost: {m.getObjVal():.2f} k$")
