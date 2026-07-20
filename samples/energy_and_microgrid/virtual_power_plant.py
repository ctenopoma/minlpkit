"""仮想発電所 (VPP) 入札・制御最適化 (Virtual Power Plant Control)

アグリゲーター(分散型電源を束ねて卸電力市場に入札する事業者)が、傘下の複数DER
(太陽光・蓄電池・小型ガスエンジンなど出力特性の異なる分散電源)の出力配分と、
市場へ提出する入札量を複数の時間コマにわたって同時に決める意思決定である。
起動に時間のかかる小型発電機はオン/オフの0-1判断(起動すれば最低出力以上を維持する
義務が生じる)を伴い、蓄電池は充放電状態が排他的である。集約した入札量が実際に
供給できる範囲を超えるとインバランス(需給乖離)ペナルティを負うため、DERの出力可能量
の範囲内でのみ入札できるという整合性制約の下で市場収益を最大化する。
"""

from pyscipopt import Model, quicksum

T = 4
DERS = ["solar", "gas_engine"]
gas_min_output = 5.0
gas_max_output = 20.0
solar_max = {0: 12.0, 1: 20.0, 2: 18.0, 3: 6.0}  # 時間帯ごとの日射に依存した上限
battery_max_power = 10.0
battery_capacity = 30.0
market_price = {0: 12.0, 1: 18.0, 2: 15.0, 3: 20.0}
gas_marginal_cost = 6.0


def build_model():
    model = Model("Virtual_Power_Plant")

    solar = {t: model.addVar(vtype="C", lb=0, ub=solar_max[t], name=f"solar_{t}") for t in range(T)}
    gas_on = {t: model.addVar(vtype="B", name=f"gas_on_{t}") for t in range(T)}
    gas = {t: model.addVar(vtype="C", lb=0, ub=gas_max_output, name=f"gas_{t}") for t in range(T)}
    chg = {t: model.addVar(vtype="C", lb=0, ub=battery_max_power, name=f"chg_{t}") for t in range(T)}
    dis = {t: model.addVar(vtype="C", lb=0, ub=battery_max_power, name=f"dis_{t}") for t in range(T)}
    soc = {t: model.addVar(vtype="C", lb=0, ub=battery_capacity, name=f"soc_{t}") for t in range(T)}
    bid = {t: model.addVar(vtype="C", lb=0, name=f"bid_{t}") for t in range(T)}

    for t in range(T):
        # ガスエンジンは起動していれば最低出力以上・最大出力以下
        model.addCons(gas[t] >= gas_min_output * gas_on[t], name=f"gas_min_{t}")
        model.addCons(gas[t] <= gas_max_output * gas_on[t], name=f"gas_max_{t}")
        model.addCons(bid[t] == solar[t] + gas[t] + dis[t] - chg[t], name=f"aggregation_{t}")
        prev_soc = 15.0 if t == 0 else soc[t - 1]
        model.addCons(soc[t] == prev_soc + chg[t] - dis[t], name=f"soc_balance_{t}")

    model.setObjective(
        quicksum(market_price[t] * bid[t] - gas_marginal_cost * gas[t] for t in range(T)),
        "maximize",
    )
    model.data = {"bid": bid, "gas_on": gas_on, "soc": soc}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Max Revenue:", m.getObjVal())
