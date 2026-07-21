"""地熱ヒートポンプ群の複数期運転計画 (Geothermal Heat Pump)

事業ストーリー
--------------
地域熱供給の運転担当者が、複数の地熱井(ヒートポンプ)について時間帯ごとに「稼働させるか
(整数のオンオフ)」「出湯温度目標をどこに設定するか」を決める。ヒートポンプの成績係数(COP)は
出湯温度が高いほど低下する物理特性があり、供給熱量は COP × 消費電力 という双線形の関係で
決まる(COPが温度目標の一次関数、供給熱量はCOPと電力の積)ため、温度目標を上げ過ぎると
同じ電力でも供給熱量がむしろ頭打ちになるトレードオフが生じる。各時間帯の暖房需要を、
稼働させた井の合計供給熱量で満たす。
"""

from pyscipopt import Model, quicksum

N_WELL, N_T = 2, 3
T_MIN, T_MAX = 30.0, 50.0
COMFORT_MIN = 40.0                  # 稼働時に満たすべき最低出湯温度
ELEC_MAX = 25.0                     # 井あたり最大消費電力[MWh]
DEMAND = [30.0, 55.0, 40.0]         # 期別暖房需要[MWh]
ELEC_PRICE = 45.0                   # 電力単価[$/MWh]
STARTUP_COST = 60.0


def build_model():
    model = Model("Geothermal_Heat_Pump")
    W, T = range(N_WELL), range(N_T)

    t_out = {(w, t): model.addVar(vtype="C", lb=T_MIN, ub=T_MAX, name=f"t_out_{w}_{t}")
             for w in W for t in T}
    elec = {(w, t): model.addVar(vtype="C", lb=0, ub=ELEC_MAX, name=f"elec_{w}_{t}")
            for w in W for t in T}
    heat = {(w, t): model.addVar(vtype="C", lb=0, name=f"heat_{w}_{t}") for w in W for t in T}
    on = {(w, t): model.addVar(vtype="B", name=f"on_{w}_{t}") for w in W for t in T}

    for w in W:
        for t in T:
            # 供給熱量 = COP(出湯温度) × 消費電力(双線形): COP = 6.0 - 0.05*(t_out-15)
            model.addCons(
                heat[w, t] == (6.0 - 0.05 * (t_out[w, t] - 15.0)) * elec[w, t],
                f"heat_def_{w}_{t}")
            model.addCons(elec[w, t] <= ELEC_MAX * on[w, t], f"elec_link_{w}_{t}")
            # 稼働時は快適基準の出湯温度を確保(非稼働時は自由=下限で無視)
            model.addCons(t_out[w, t] >= COMFORT_MIN * on[w, t], f"comfort_{w}_{t}")

    for t in T:
        model.addCons(quicksum(heat[w, t] for w in W) >= DEMAND[t], f"demand_{t}")

    elec_cost = quicksum(ELEC_PRICE * elec[w, t] for w in W for t in T)
    startup = quicksum(STARTUP_COST * on[w, t] for w in W for t in T)
    model.setObjective(elec_cost + startup, "minimize")

    model.data = {"t_out": t_out, "elec": elec, "heat": heat, "on": on}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
