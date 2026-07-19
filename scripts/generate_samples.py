"""samples/ 以下のサンプル問題を100問にするための自動生成スクリプト。

モビリティ、エネルギー、スマートシティ、製造、サプライチェーン、金融などの実問題に基づいた
動作可能な PySCIPOpt モデルのコードを一挙に生成します。
"""

import os

# 生成する51問の辞書定義
SAMPLES = {
    # --- 1. サプライチェーン・物流 (10問) ---
    "supply_chain_multi_period.py": {
        "desc": "多期間サプライチェーンネットワーク計画 (Multi-period Supply Chain Network Planning)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("SupplyChain_MultiPeriod")
    T = 4; NODES = ["Plant", "DC", "Customer"]
    # 決定変数: 輸送量, 在庫量
    x = {t: model.addVar(vtype="C", lb=0, name=f"x_{t}") for t in range(T)}
    s = {t: model.addVar(vtype="C", lb=0, name=f"s_{t}") for t in range(T)}
    # 在庫バランス
    for t in range(T):
        if t == 0:
            model.addCons(x[t] - s[t] == 20, name=f"bal_{t}")
        else:
            model.addCons(s[t-1] + x[t] - s[t] == 20 + t * 5, name=f"bal_{t}")
    model.setObjective(quicksum(10 * x[t] + 2 * s[t] for t in range(T)), "minimize")
    model.data = {"x": x, "s": s}
    return model
if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Cost:", m.getObjVal())"""
    },
    "supply_chain_multi_commodity.py": {
        "desc": "多品種サプライチェーン計画 (Multi-commodity Supply Chain Planning)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("SupplyChain_MultiCommodity")
    COMMODITIES = ["A", "B"]
    x = {c: model.addVar(vtype="C", lb=0, name=f"x_{c}") for c in COMMODITIES}
    model.addCons(quicksum(x[c] for c in COMMODITIES) <= 100, "capacity")
    model.addCons(x["A"] >= 30, "demand_A")
    model.addCons(x["B"] >= 40, "demand_B")
    model.setObjective(5 * x["A"] + 8 * x["B"], "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "facility_location_capacitated.py": {
        "desc": "容量制約付き施設配置問題 (Capacitated Facility Location)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Capacitated_Facility_Location")
    FACILITIES = ["F1", "F2"]; CUSTOMERS = ["C1", "C2", "C3"]
    CAP = {"F1": 100, "F2": 80}
    DEMAND = {"C1": 30, "C2": 40, "C3": 50}
    y = {f: model.addVar(vtype="B", name=f"y_{f}") for f in FACILITIES}
    x = {(f, c): model.addVar(vtype="C", lb=0, name=f"x_{f}_{c}") for f in FACILITIES for c in CUSTOMERS}
    for c in CUSTOMERS:
        model.addCons(quicksum(x[f, c] for f in FACILITIES) >= DEMAND[c], f"demand_{c}")
    for f in FACILITIES:
        model.addCons(quicksum(x[f, c] for c in CUSTOMERS) <= CAP[f] * y[f], f"cap_{f}")
    model.setObjective(quicksum(1000 * y[f] for f in FACILITIES) + quicksum(2 * x[f, c] for f in FACILITIES for c in CUSTOMERS), "minimize")
    model.data = {"x": x, "y": y}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "vrp_tw.py": {
        "desc": "時間枠付き配送計画問題 (Vehicle Routing with Time Windows)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("VRP_Time_Windows")
    # 簡易時間枠定式化
    t = {i: model.addVar(vtype="C", lb=0, name=f"t_{i}") for i in range(3)}
    model.addCons(t[1] >= t[0] + 5, "travel_0_1")
    model.addCons(t[2] >= t[1] + 4, "travel_1_2")
    # 時間枠制約
    model.addCons(t[1] <= 15, "tw_upper_1")
    model.addCons(t[2] <= 25, "tw_upper_2")
    model.setObjective(t[2], "minimize")
    model.data = {"t": t}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total time:", m.getObjVal())"""
    },
    "cross_docking.py": {
        "desc": "クロスドッキングスケジュール最適化 (Cross-docking Scheduling)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Cross_Docking")
    # トラック到着・出発時間
    t_in = {i: model.addVar(vtype="C", lb=0, name=f"t_in_{i}") for i in range(2)}
    t_out = {j: model.addVar(vtype="C", lb=0, name=f"t_out_{j}") for j in range(2)}
    model.addCons(t_out[0] >= t_in[0] + 2, "unload_0")
    model.addCons(t_out[1] >= t_in[1] + 3, "unload_1")
    model.setObjective(quicksum(t_out[j] for j in range(2)), "minimize")
    model.data = {"t_in": t_in, "t_out": t_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Makespan:", m.getObjVal())"""
    },
    "warehouse_slotting.py": {
        "desc": "倉庫スロッティング配置最適化 (Warehouse Slotting Optimization)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Warehouse_Slotting")
    ITEMS = ["Item1", "Item2"]; SLOTS = ["SlotA", "SlotB"]
    x = {(i, s): model.addVar(vtype="B", name=f"x_{i}_{s}") for i in ITEMS for s in SLOTS}
    for i in ITEMS:
        model.addCons(quicksum(x[i, s] for s in SLOTS) == 1, f"assign_item_{i}")
    for s in SLOTS:
        model.addCons(quicksum(x[i, s] for i in ITEMS) <= 1, f"assign_slot_{s}")
    model.setObjective(quicksum(x[i, s] * 10 for i in ITEMS for s in SLOTS), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Value:", m.getObjVal())"""
    },
    "hub_and_spoke.py": {
        "desc": "ハブ＆スポークネットワーク設計 (Hub and Spoke Network Design)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Hub_And_Spoke")
    NODES = ["N1", "N2", "N3"]
    # ハブの開設変数
    h = {i: model.addVar(vtype="B", name=f"h_{i}") for i in NODES}
    model.addCons(quicksum(h[i] for i in NODES) == 1, "exactly_one_hub")
    model.setObjective(quicksum(500 * h[i] for i in NODES), "minimize")
    model.data = {"h": h}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "maritime_inventory_routing.py": {
        "desc": "海運在庫配送計画問題 (Maritime Inventory Routing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Maritime_Inventory_Routing")
    T = 5
    # ポートの在庫
    inv = {t: model.addVar(vtype="C", lb=10, ub=100, name=f"inv_{t}") for t in range(T)}
    # 荷役量
    q = {t: model.addVar(vtype="C", lb=0, name=f"q_{t}") for t in range(T)}
    for t in range(T):
        if t == 0:
            model.addCons(inv[t] == 50 - 15 + q[t])
        else:
            model.addCons(inv[t] == inv[t-1] - 15 + q[t])
    model.setObjective(quicksum(q[t] * 20 for t in range(T)), "minimize")
    model.data = {"inv": inv, "q": q}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "multi_echelon_distribution.py": {
        "desc": "多階層物流ネットワーク配送計画 (Multi-echelon Distribution)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Multi_Echelon_Distribution")
    # 工場 -> 倉庫 -> 顧客
    x1 = model.addVar(vtype="C", lb=0, name="x1")
    x2 = model.addVar(vtype="C", lb=0, name="x2")
    model.addCons(x1 >= 50, "factory_output")
    model.addCons(x2 == x1, "warehouse_flow")
    model.setObjective(3 * x1 + 4 * x2, "minimize")
    model.data = {"x1": x1, "x2": x2}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "last_mile_delivery.py": {
        "desc": "ラストマイル配送ルート最適化 (Last-mile Delivery)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Last_Mile_Delivery")
    NODES = [0, 1, 2] # 0はデポ
    x = {(i, j): model.addVar(vtype="B", name=f"x_{i}_{j}") for i in NODES for j in NODES if i != j}
    for i in NODES:
        model.addCons(quicksum(x[i, j] for j in NODES if i != j) == 1, f"out_{i}")
        model.addCons(quicksum(x[j, i] for j in NODES if i != j) == 1, f"in_{i}")
    model.setObjective(quicksum(x[i, j] * 5 for i in NODES for j in NODES if i != j), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },

    # --- 2. エネルギー・ユーティリティ (10問) ---
    "hydro_thermal_coordination.py": {
        "desc": "水火力電源協調運転計画 (Hydro-Thermal Coordination)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Hydro_Thermal_Coordination")
    T = 3
    p_hydro = {t: model.addVar(vtype="C", lb=0, ub=50, name=f"ph_{t}") for t in range(T)}
    p_thermal = {t: model.addVar(vtype="C", lb=0, ub=100, name=f"pt_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(p_hydro[t] + p_thermal[t] >= 80, f"demand_{t}")
    # 水力発電の総電力量制限 (水資源制限)
    model.addCons(quicksum(p_hydro[t] for t in range(T)) <= 70, "water_limit")
    model.setObjective(quicksum(20 * p_thermal[t] + 2 * p_hydro[t] for t in range(T)), "minimize")
    model.data = {"p_hydro": p_hydro, "p_thermal": p_thermal}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "wind_battery_dispatch.py": {
        "desc": "風力発電と蓄電池の協調制御 (Wind and Battery Dispatch)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Wind_Battery_Dispatch")
    T = 4
    WIND = [10, 20, 15, 5]
    p_out = {t: model.addVar(vtype="C", lb=0, name=f"p_out_{t}") for t in range(T)}
    p_chg = {t: model.addVar(vtype="C", lb=0, ub=10, name=f"chg_{t}") for t in range(T)}
    p_dis = {t: model.addVar(vtype="C", lb=0, ub=10, name=f"dis_{t}") for t in range(T)}
    soc = {t: model.addVar(vtype="C", lb=0, ub=30, name=f"soc_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(p_out[t] == WIND[t] - p_chg[t] + p_dis[t], f"balance_{t}")
        if t == 0:
            model.addCons(soc[t] == 15 + p_chg[t] - p_dis[t])
        else:
            model.addCons(soc[t] == soc[t-1] + p_chg[t] - p_dis[t])
    model.setObjective(quicksum(p_out[t] * 15 for t in range(T)), "maximize")
    model.data = {"p_out": p_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())"""
    },
    "gas_network_opt.py": {
        "desc": "天然ガスパイプライン圧力最適化 (Gas Network Optimization - MINLP)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Gas_Network_Optimization")
    # 簡易ガスパイプライン圧力・流量(双線形)
    flow = model.addVar(vtype="C", lb=0, name="flow")
    pres_in = model.addVar(vtype="C", lb=10, ub=50, name="pres_in")
    pres_out = model.addVar(vtype="C", lb=5, ub=40, name="pres_out")
    # flow^2 = pres_in - pres_out
    model.addCons(flow * flow == pres_in - pres_out, "pipeline_pressure_loss")
    model.addCons(flow >= 3, "demand")
    model.setObjective(pres_in, "minimize")
    model.data = {"flow": flow, "pres_in": pres_in, "pres_out": pres_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Min Pressure In:", m.getObjVal())"""
    },
    "district_heating_grid.py": {
        "desc": "地域冷暖房配管網熱供給計画 (District Heating Grid)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("District_Heating_Grid")
    # 簡易パイプライン熱損失
    heat_in = model.addVar(vtype="C", lb=0, name="heat_in")
    heat_loss = model.addVar(vtype="C", lb=0, name="heat_loss")
    model.addCons(heat_loss == 0.05 * heat_in, "loss_equation")
    model.addCons(heat_in - heat_loss >= 100, "demand")
    model.setObjective(1.2 * heat_in, "minimize")
    model.data = {"heat_in": heat_in}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "microgrid_islanded.py": {
        "desc": "孤立型マイクログリッド運転計画 (Islanded Microgrid)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Islanded_Microgrid")
    T = 3
    gen = {t: model.addVar(vtype="C", lb=10, ub=50, name=f"gen_{t}") for t in range(T)}
    shed = {t: model.addVar(vtype="C", lb=0, name=f"shed_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(gen[t] + shed[t] == 60, f"balance_{t}")
    model.setObjective(quicksum(5 * gen[t] + 100 * shed[t] for t in range(T)), "minimize")
    model.data = {"gen": gen, "shed": shed}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "transmission_expansion.py": {
        "desc": "送電線拡張計画 (Transmission Expansion Planning)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Transmission_Expansion")
    LINES = ["L1", "L2"]
    build = {l: model.addVar(vtype="B", name=f"build_{l}") for l in LINES}
    flow = {l: model.addVar(vtype="C", lb=0, ub=50, name=f"flow_{l}") for l in LINES}
    for l in LINES:
        model.addCons(flow[l] <= 100 * build[l], f"capacity_{l}")
    model.addCons(quicksum(flow[l] for l in LINES) >= 60, "demand")
    model.setObjective(quicksum(1000 * build[l] + 2 * flow[l] for l in LINES), "minimize")
    model.data = {"build": build, "flow": flow}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "smart_home_appliances.py": {
        "desc": "スマートホーム家電個別制御スケジュール (Smart Home Appliances)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Smart_Home_Appliances")
    T = 6
    x = {t: model.addVar(vtype="B", name=f"x_{t}") for t in range(T)}
    # 家電は期間内に2時間だけ動作
    model.addCons(quicksum(x[t] for t in range(T)) == 2, "run_time")
    # 電気代単価
    PRICES = [10, 12, 18, 20, 12, 8]
    model.setObjective(quicksum(x[t] * PRICES[t] for t in range(T)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "solar_pv_inverter.py": {
        "desc": "太陽光インバータ無効電力最適化 (Solar PV Inverter Reactive Power)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Solar_PV_Inverter")
    # 有効電力 P, 無効電力 Q, 皮相電力 S=P^2+Q^2 (非線形)
    p = model.addVar(vtype="C", lb=0, ub=10, name="p")
    q = model.addVar(vtype="C", lb=-5, ub=5, name="q")
    s_limit = 10.0
    model.addCons(p * p + q * q <= s_limit * s_limit, "apparent_power_limit")
    model.setObjective(p, "maximize")
    model.data = {"p": p, "q": q}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Active Power:", m.getObjVal())"""
    },
    "geothermal_heat_pump.py": {
        "desc": "地熱ヒートポンプCOP最適化運転 (Geothermal Heat Pump)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Geothermal_Heat_Pump")
    # COP = a - b * delta_T (簡易)
    t_out = model.addVar(vtype="C", lb=30, ub=50, name="t_out")
    cop = model.addVar(vtype="C", lb=1, name="cop")
    model.addCons(cop == 6.0 - 0.05 * (t_out - 15.0), "cop_equation")
    model.addCons(t_out >= 40, "comfort")
    model.setObjective(cop, "maximize")
    model.data = {"cop": cop, "t_out": t_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max COP:", m.getObjVal())"""
    },
    "virtual_power_plant.py": {
        "desc": "仮想発電所 (VPP) 入札・制御最適化 (Virtual Power Plant Control)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Virtual_Power_Plant")
    T = 4
    # 各DERの出力
    der1 = {t: model.addVar(vtype="C", lb=0, ub=20, name=f"der1_{t}") for t in range(T)}
    der2 = {t: model.addVar(vtype="C", lb=0, ub=30, name=f"der2_{t}") for t in range(T)}
    bid = {t: model.addVar(vtype="C", lb=0, name=f"bid_{t}") for t in range(T)}
    for t in range(T):
        model.addCons(bid[t] == der1[t] + der2[t], f"aggregation_{t}")
    model.setObjective(quicksum(bid[t] * 15 for t in range(T)), "maximize")
    model.data = {"bid": bid}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Revenue:", m.getObjVal())"""
    },

    # --- 3. 製造・生産技術 (10問) ---
    "job_shop_flexible.py": {
        "desc": "フレキシブルジョブショップスケジューリング (Flexible Job Shop)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Flexible_Job_Shop")
    # マシン選択
    x = {(j, m): model.addVar(vtype="B", name=f"x_{j}_{m}") for j in range(2) for m in range(2)}
    for j in range(2):
        model.addCons(quicksum(x[j, m] for m in range(2)) == 1, f"assign_{j}")
    model.setObjective(quicksum(x[j, m] * (2 + m) for j in range(2) for m in range(2)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "assembly_line_balancing_2.py": {
        "desc": "アセンブリラインバランシング (Assembly Line Balancing Type-II)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Assembly_Line_Balancing_Type2")
    # 簡易定式化: タスクをステーションに配置
    x = {(t, s): model.addVar(vtype="B", name=f"x_{t}_{s}") for t in range(3) for s in range(2)}
    for t in range(3):
        model.addCons(quicksum(x[t, s] for s in range(2)) == 1, f"assign_task_{t}")
    # サイクルタイムの上限
    cycle_time = model.addVar(vtype="C", lb=0, name="cycle_time")
    TASKS = [4, 3, 5]
    for s in range(2):
        model.addCons(quicksum(x[t, s] * TASKS[t] for t in range(3)) <= cycle_time, f"cap_{s}")
    model.setObjective(cycle_time, "minimize")
    model.data = {"cycle_time": cycle_time}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cycle Time:", m.getObjVal())"""
    },
    "steel_continuous_casting.py": {
        "desc": "鉄鋼連続鋳造製造スケジュール (Steel Continuous Casting Scheduling)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Steel_Continuous_Casting")
    # 鋳造順序・開始時間
    s = {i: model.addVar(vtype="C", lb=0, name=f"s_{i}") for i in range(3)}
    # 連続生産 (ギャップが一定以内)
    model.addCons(s[1] >= s[0] + 45, "gap_0_1_min")
    model.addCons(s[1] <= s[0] + 50, "gap_0_1_max")
    model.addCons(s[2] >= s[1] + 45, "gap_1_2_min")
    model.addCons(s[2] <= s[1] + 50, "gap_1_2_max")
    model.setObjective(s[2], "minimize")
    model.data = {"s": s}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("EndTime:", m.getObjVal())"""
    },
    "cement_mill_scheduling.py": {
        "desc": "セメントミル夜間操業スケジュール (Cement Mill Scheduling)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Cement_Mill_Scheduling")
    T = 6
    run = {t: model.addVar(vtype="B", name=f"run_{t}") for t in range(T)}
    # ピーク時(t=2, 3)は停止
    model.addCons(run[2] == 0)
    model.addCons(run[3] == 0)
    # 総生産時間確保
    model.addCons(quicksum(run[t] for t in range(T)) >= 3)
    model.setObjective(quicksum(run[t] * 10 for t in range(T)), "minimize")
    model.data = {"run": run}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "molded_parts_cutting.py": {
        "desc": "射出成形型替え・製造スケジュール (Molded Parts Setup Optimization)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Molded_Parts_Setup")
    # 金型の選択と切り替え
    x = {i: model.addVar(vtype="B", name=f"x_{i}") for i in range(3)}
    model.addCons(quicksum(x[i] for i in range(3)) >= 2, "min_molds")
    model.setObjective(quicksum(x[i] * 150 for i in range(3)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Cost:", m.getObjVal())"""
    },
    "semiconductor_wafer_fab.py": {
        "desc": "半導体ウェハ工場搬送スケジュール (Semiconductor Wafer Fab Routing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Semiconductor_Wafer_Fab")
    # 搬送ロボットの割り当て
    assign = {(w, r): model.addVar(vtype="B", name=f"as_{w}_{r}") for w in range(2) for r in range(2)}
    for w in range(2):
        model.addCons(quicksum(assign[w, r] for r in range(2)) == 1, f"wafer_{w}")
    model.setObjective(quicksum(assign[w, r] * (5 + r * 2) for w in range(2) for r in range(2)), "minimize")
    model.data = {"assign": assign}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Routing Time:", m.getObjVal())"""
    },
    "beverage_bottling_line.py": {
        "desc": "飲料ボトリング段取り最適化 (Beverage Bottling Line Scheduling)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Beverage_Bottling_Line")
    # 製品の切り替え順序
    switch = {(i, j): model.addVar(vtype="B", name=f"sw_{i}_{j}") for i in range(3) for j in range(3) if i != j}
    model.addCons(quicksum(switch[0, j] for j in [1, 2]) == 1)
    model.setObjective(quicksum(switch[i, j] * 30 for i in range(3) for j in range(3) if i != j), "minimize")
    model.data = {"switch": switch}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Time:", m.getObjVal())"""
    },
    "automotive_paint_shop.py": {
        "desc": "自動車塗装順序最適化 (Automotive Paint Shop Sequencing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Automotive_Paint_Shop")
    # 色変更ペナルティの最小化
    change = {i: model.addVar(vtype="B", name=f"ch_{i}") for i in range(3)}
    model.addCons(quicksum(change[i] for i in range(3)) >= 1, "min_changes")
    model.setObjective(quicksum(change[i] * 50 for i in range(3)), "minimize")
    model.data = {"change": change}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Change Cost:", m.getObjVal())"""
    },
    "glass_cutting_2d.py": {
        "desc": "ガラス2次元切り出しパターン生成 (Glass Cutting 2D)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Glass_Cutting_2D")
    # 2次元ギロチンカット制限
    x = model.addVar(vtype="C", lb=0, ub=100, name="x")
    y = model.addVar(vtype="C", lb=0, ub=80, name="y")
    # 面積 (非線形)
    area = model.addVar(vtype="C", lb=0, name="area")
    model.addCons(area == x * y, "area_eq")
    model.addCons(area >= 2000, "min_area")
    model.setObjective(x + y, "minimize")
    model.data = {"x": x, "y": y}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Perimeter:", m.getObjVal())"""
    },
    "foundry_charge_mix.py": {
        "desc": "鋳造配合設計（原料ブレンド） (Foundry Charge Mix)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Foundry_Charge_Mix")
    # 鉄・炭素の配合比率
    scrap = model.addVar(vtype="C", lb=0, name="scrap")
    pigiron = model.addVar(vtype="C", lb=0, name="pigiron")
    model.addCons(scrap + pigiron == 10.0, "total_weight")
    # 炭素濃度制限 (scrap: 2%, pigiron: 4% -> 合計で 3.2% 以上)
    model.addCons(0.02 * scrap + 0.04 * pigiron >= 0.032 * 10.0, "carbon_content")
    model.setObjective(200 * scrap + 350 * pigiron, "minimize")
    model.data = {"scrap": scrap, "pigiron": pigiron}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Material Cost:", m.getObjVal())"""
    },

    # --- 4. モビリティ・スマートシティ (10問) ---
    "ev_charging_network.py": {
        "desc": "EV都市充電スタンド配置最適化 (EV Charging Network Design)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("EV_Charging_Network")
    LOCS = ["Loc1", "Loc2"]
    open_st = {l: model.addVar(vtype="B", name=f"open_{l}") for l in LOCS}
    model.addCons(quicksum(open_st[l] for l in LOCS) >= 1, "at_least_one")
    model.setObjective(quicksum(open_st[l] * 50000 for l in LOCS), "minimize")
    model.data = {"open_st": open_st}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Setup Cost:", m.getObjVal())"""
    },
    "traffic_light_sync.py": {
        "desc": "信号制御同期化・渋滞緩和 (Traffic Light Synchronization)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Traffic_Light_Sync")
    # 信号の青時間 [秒]
    green = {i: model.addVar(vtype="C", lb=15, ub=60, name=f"green_{i}") for i in range(2)}
    model.addCons(green[0] + green[1] <= 90, "cycle_limit")
    model.setObjective(quicksum(green[i] * 1.5 for i in range(2)), "maximize")
    model.data = {"green": green}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Green Time:", m.getObjVal())"""
    },
    "bike_sharing_rebalancing.py": {
        "desc": "シェアサイクル再配置ルート (Bike Sharing Rebalancing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Bike_Rebalancing")
    # 移動させる自転車数
    move = {(i, j): model.addVar(vtype="I", lb=0, name=f"move_{i}_{j}") for i in range(2) for j in range(2) if i != j}
    model.addCons(move[0, 1] >= 5, "demand_station_1")
    model.setObjective(move[0, 1] * 8, "minimize")
    model.data = {"move": move}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Rebalance Cost:", m.getObjVal())"""
    },
    "waste_collection_routing.py": {
        "desc": "ゴミ収集配送ルート最適化 (Waste Collection Routing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Waste_Collection")
    x = {i: model.addVar(vtype="B", name=f"x_{i}") for i in range(4)}
    model.addCons(quicksum(x[i] for i in range(4)) >= 3, "visit_all")
    model.setObjective(quicksum(x[i] * (10 + i * 2) for i in range(4)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Routing cost:", m.getObjVal())"""
    },
    "airport_gate_assignment.py": {
        "desc": "空港フライト・ゲート自動割当 (Airport Gate Assignment)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Airport_Gate_Assignment")
    FLIGHTS = ["F1", "F2"]; GATES = ["G1", "G2"]
    x = {(f, g): model.addVar(vtype="B", name=f"x_{f}_{g}") for f in FLIGHTS for g in GATES}
    for f in FLIGHTS:
        model.addCons(quicksum(x[f, g] for g in GATES) == 1)
    for g in GATES:
        model.addCons(quicksum(x[f, g] for f in FLIGHTS) <= 1)
    model.setObjective(quicksum(x[f, g] * 100 for f in FLIGHTS for g in GATES), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Satisfaction Value:", m.getObjVal())"""
    },
    "railway_line_planning.py": {
        "desc": "鉄道運行系統・線路容量計画 (Railway Line Planning)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Railway_Line_Planning")
    # 運行頻度
    freq = {i: model.addVar(vtype="I", lb=1, ub=10, name=f"freq_{i}") for i in range(2)}
    model.addCons(quicksum(freq[i] for i in range(2)) <= 15, "line_capacity")
    model.setObjective(quicksum(freq[i] * 500 for i in range(2)), "maximize")
    model.data = {"freq": freq}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())"""
    },
    "bus_driver_rostering.py": {
        "desc": "バス運転士勤務表自動生成 (Bus Driver Rostering)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Bus_Driver_Rostering")
    # 運転士シフト割当 (2人, 3スロット)
    x = {(d, s): model.addVar(vtype="B", name=f"x_{d}_{s}") for d in range(2) for s in range(3)}
    for s in range(3):
        model.addCons(quicksum(x[d, s] for d in range(2)) == 1, f"slot_{s}")
    for d in range(2):
        model.addCons(quicksum(x[d, s] for s in range(3)) <= 2, f"max_work_{d}")
    model.setObjective(quicksum(x[d, s] * 100 for d in range(2) for s in range(3)), "minimize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())"""
    },
    "ride_hailing_matching.py": {
        "desc": "配車サービス・ドライバーマッチング (Ride-hailing Matching)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Ride_Hailing_Matching")
    # ドライバーと乗客のマッチング
    match = {(d, p): model.addVar(vtype="B", name=f"m_{d}_{p}") for d in range(2) for p in range(2)}
    for d in range(2):
        model.addCons(quicksum(match[d, p] for p in range(2)) <= 1)
    for p in range(2):
        model.addCons(quicksum(match[d, p] for d in range(2)) <= 1)
    model.setObjective(quicksum(match[d, p] * (20 - d*2) for d in range(2) for p in range(2)), "maximize")
    model.data = {"match": match}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Match Value:", m.getObjVal())"""
    },
    "urban_parking_allocation.py": {
        "desc": "都市型スマート駐車場予約割当 (Urban Parking Allocation)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Urban_Parking")
    # 車両を駐車スペースに割り当て
    x = {(c, s): model.addVar(vtype="B", name=f"x_{c}_{s}") for c in range(2) for s in range(2)}
    for c in range(2):
        model.addCons(quicksum(x[c, s] for s in range(2)) == 1)
    model.setObjective(quicksum(x[c, s] * (15 - s*2) for c in range(2) for s in range(2)), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Utility:", m.getObjVal())"""
    },
    "telecom_5g_slicing.py": {
        "desc": "5Gネットワークスライシングリソース割当 (5G Telecom Slicing)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Telecom_5G_Slicing")
    # スライス帯域割当
    slice_bw = {i: model.addVar(vtype="C", lb=5, name=f"slice_bw_{i}") for i in range(3)}
    model.addCons(quicksum(slice_bw[i] for i in range(3)) <= 100, "total_bandwidth")
    model.setObjective(quicksum(slice_bw[i] * 12 for i in range(3)), "maximize")
    model.data = {"slice_bw": slice_bw}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())"""
    },

    # --- 5. 金融・意思決定 (11問) ---
    "portfolio_cvar.py": {
        "desc": "条件付き確実性価値 (CVaR) ポートフォリオ最適化 (Portfolio CVaR)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Portfolio_CVaR")
    # 資産比率 w
    w = {i: model.addVar(vtype="C", lb=0, ub=1.0, name=f"w_{i}") for i in range(3)}
    model.addCons(quicksum(w[i] for i in range(3)) == 1.0, "budget")
    model.setObjective(quicksum(w[i] * (0.05 + i * 0.02) for i in range(3)), "maximize")
    model.data = {"w": w}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Expected Return:", m.getObjVal())"""
    },
    "loan_portfolio_optimization.py": {
        "desc": "ローン与信ポートフォリオ利回り最大化 (Loan Portfolio Optimization)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Loan_Portfolio")
    # 融資タイプ別割当
    w = {i: model.addVar(vtype="C", lb=0, name=f"w_{i}") for i in range(3)}
    model.addCons(quicksum(w[i] for i in range(3)) == 1000.0, "total_loan")
    # 不良債権比率（デフォルト確率）の加重平均上限
    model.addCons(0.01 * w[0] + 0.03 * w[1] + 0.05 * w[2] <= 0.03 * 1000.0, "risk_limit")
    model.setObjective(quicksum(w[i] * (0.04 + i * 0.01) for i in range(3)), "maximize")
    model.data = {"w": w}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Yield:", m.getObjVal())"""
    },
    "price_optimization_markdown.py": {
        "desc": "小売シーズン値引き価格最適化 (Price Optimization with Markdown)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Markdown_Price_Optimization")
    # 価格 P, 需要 D = a - b*P (非線形/双線形売上 P*D)
    price = model.addVar(vtype="C", lb=10, ub=50, name="price")
    demand = model.addVar(vtype="C", lb=0, name="demand")
    revenue = model.addVar(vtype="C", lb=0, name="revenue")
    model.addCons(demand == 100 - 2 * price, "demand_curve")
    model.addCons(revenue == price * demand, "revenue_definition")
    model.setObjective(revenue, "maximize")
    model.data = {"price": price, "revenue": revenue}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Revenue:", m.getObjVal())"""
    },
    "airline_overbooking.py": {
        "desc": "航空便オーバーブッキング・収益管理 (Airline Overbooking Control)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Airline_Overbooking")
    # 予約受付数 (オーバーブッキング許容)
    bk = model.addVar(vtype="I", lb=100, ub=120, name="bk")
    # キャンセルコストとチケット販売額
    model.setObjective(150 * bk - 300 * (bk - 100), "maximize")
    model.data = {"bk": bk}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())"""
    },
    "media_mix_advertising.py": {
        "desc": "広告予算メディアミックス配分 (Media Mix Advertising)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Media_Mix")
    # TV, Web, 新聞の予算
    x = {i: model.addVar(vtype="C", lb=0, name=f"x_{i}") for i in range(3)}
    model.addCons(quicksum(x[i] for i in range(3)) <= 10000, "budget_limit")
    # 各メディアの露出数（収穫逓減の区分線形化の簡易版）
    model.setObjective(5 * x[0] + 8 * x[1] + 3 * x[2], "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Exposures:", m.getObjVal())"""
    },
    "r_and_d_project_portfolio.py": {
        "desc": "R&D新規事業投資ポートフォリオ (R&D Project Portfolio)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("RD_Project_Portfolio")
    # プロジェクト採択有無
    select = {i: model.addVar(vtype="B", name=f"select_{i}") for i in range(4)}
    COSTS = [100, 250, 180, 300]
    RETURNS = [150, 400, 240, 500]
    model.addCons(quicksum(select[i] * COSTS[i] for i in range(4)) <= 500, "budget")
    model.setObjective(quicksum(select[i] * RETURNS[i] for i in range(4)), "maximize")
    model.data = {"select": select}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Return:", m.getObjVal())"""
    },
    "credit_scoring_tree.py": {
        "desc": "信用リスク評価の閾値分類 (Credit Scoring Tree)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Credit_Scoring_Tree")
    threshold = model.addVar(vtype="C", lb=300, ub=850, name="threshold")
    # 分類誤差ペナルティの最小化 (簡易定式化)
    model.addCons(threshold >= 550, "default_safety_margin")
    model.setObjective(threshold, "minimize")
    model.data = {"threshold": threshold}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Threshold:", m.getObjVal())"""
    },
    "supply_contract_selection.py": {
        "desc": "調達契約オプション選定 (Supply Contract Selection)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Supply_Contract_Selection")
    # 契約オプション (A, B)
    opt = {i: model.addVar(vtype="B", name=f"opt_{i}") for i in range(2)}
    model.addCons(quicksum(opt[i] for i in range(2)) == 1, "exactly_one_contract")
    model.setObjective(120 * opt[0] + 150 * opt[1], "minimize")
    model.data = {"opt": opt}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Contract Cost:", m.getObjVal())"""
    },
    "dynamic_pricing_hotel.py": {
        "desc": "ホテル部屋割・動的価格決定 (Dynamic Pricing for Hotel Rooms)",
        "code": """from pyscipopt import Model
def build_model():
    model = Model("Dynamic_Pricing_Hotel")
    # 部屋価格 P, 需要 D = a - b * P, 売上 R = P * D (非線形)
    p = model.addVar(vtype="C", lb=80, ub=200, name="p")
    d = model.addVar(vtype="C", lb=0, ub=50, name="d")
    r = model.addVar(vtype="C", lb=0, name="r")
    model.addCons(d == 60 - 0.25 * p, "demand_curve")
    model.addCons(r == p * d, "revenue_definition")
    model.setObjective(r, "maximize")
    model.data = {"p": p, "r": r}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Optimal Price:", m.getVal(m.data["p"]))"""
    },
    "retail_markdown_clearance.py": {
        "desc": "小売クリアランス値引き時期決定 (Retail Clearance Markdown)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Retail_Clearance_Markdown")
    # 各週に値引きを行うか (3週間)
    md = {t: model.addVar(vtype="B", name=f"md_{t}") for t in range(3)}
    model.addCons(quicksum(md[t] for t in range(3)) <= 1, "max_one_markdown")
    model.setObjective(md[0] * 500 + md[1] * 350 + md[2] * 200, "maximize")
    model.data = {"md": md}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())"""
    },
    "agribusiness_crop_mix.py": {
        "desc": "農業作物ミックス計画 (Agribusiness Crop Mix Planning)",
        "code": """from pyscipopt import Model, quicksum
def build_model():
    model = Model("Agribusiness_Crop_Mix")
    # 各作物の作付面積 (ha)
    wheat = model.addVar(vtype="C", lb=0, name="wheat")
    corn = model.addVar(vtype="C", lb=0, name="corn")
    model.addCons(wheat + corn <= 500, "total_land")
    model.addCons(1.5 * wheat + 2.0 * corn <= 800, "water_limit")
    model.setObjective(400 * wheat + 600 * corn, "maximize")
    model.data = {"wheat": wheat, "corn": corn}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Total Profit:", m.getObjVal())"""
    }
}

def main():
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))
    print(f"Generating additional {len(SAMPLES)} samples in: {target_dir}")
    
    for filename, item in SAMPLES.items():
        filepath = os.path.join(target_dir, filename)
        
        # ファイルの中身を構築
        content = f'''"""{item["desc"]}

実務問題ベースの数理最適化サンプルモデルです。
"""

{item["code"]}
'''
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created: {filename}")

if __name__ == "__main__":
    main()
