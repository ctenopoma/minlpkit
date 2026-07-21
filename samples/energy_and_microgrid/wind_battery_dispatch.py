"""風力発電と蓄電池の協調制御 (Wind and Battery Dispatch)

再生可能エネルギー事業者の運用担当者が、変動する風力発電出力を蓄電池でどう平準化して
市場へ売電するかを複数の時間コマにわたって決める意思決定である。風力出力は気象条件で
その都度決まる外生量であり、余剰分を充電するか市場価格が高い時間帯に放電するかという
充放電判断が売電収益を左右する。充電と放電を同時には行えない(排他)ため0-1の充放電
モード変数を導入し、蓄電池の残量(SOC)が時間を跨いで連続的に繰り越されるという
動的な結合を通じて、単一時刻ではなく時系列全体で収益を最大化する必要がある。
"""

from pyscipopt import Model, quicksum

T = 6
WIND = [10, 20, 15, 5, 8, 18]
market_price = [15.0, 12.0, 18.0, 22.0, 20.0, 14.0]
battery_max_power = 10.0
battery_capacity = 30.0
BIG_M = battery_max_power


def build_model():
    model = Model("Wind_Battery_Dispatch")

    p_out = {t: model.addVar(vtype="C", lb=0, name=f"p_out_{t}") for t in range(T)}
    p_chg = {t: model.addVar(vtype="C", lb=0, ub=battery_max_power, name=f"chg_{t}") for t in range(T)}
    p_dis = {t: model.addVar(vtype="C", lb=0, ub=battery_max_power, name=f"dis_{t}") for t in range(T)}
    soc = {t: model.addVar(vtype="C", lb=0, ub=battery_capacity, name=f"soc_{t}") for t in range(T)}
    is_charging = {t: model.addVar(vtype="B", name=f"is_charging_{t}") for t in range(T)}

    for t in range(T):
        model.addCons(p_out[t] == WIND[t] - p_chg[t] + p_dis[t], name=f"balance_{t}")
        prev_soc = 15.0 if t == 0 else soc[t - 1]
        model.addCons(soc[t] == prev_soc + p_chg[t] - p_dis[t], name=f"soc_balance_{t}")
        # 充電と放電は同時に行えない(排他的モード)
        model.addCons(p_chg[t] <= BIG_M * is_charging[t], name=f"chg_mode_{t}")
        model.addCons(p_dis[t] <= BIG_M * (1 - is_charging[t]), name=f"dis_mode_{t}")

    model.setObjective(quicksum(p_out[t] * market_price[t] for t in range(T)), "maximize")
    model.data = {"p_out": p_out, "soc": soc, "is_charging": is_charging}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Revenue:", m.getObjVal())
