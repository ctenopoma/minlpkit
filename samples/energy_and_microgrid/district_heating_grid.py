"""地域熱供給網の熱源配分計画 (District Heating Grid)

事業ストーリー
--------------
地域熱供給(DHC)事業者の運転担当者が、複数の熱源(CHPプラント・ガス炊きボイラー)を
複数の時間帯についてどれだけ稼働させるかを決める。配管網の熱損失は流量が増えるほど
摩擦損失で急増する(流量の2乗に比例する物理現象)ため、少数の熱源に集中させて配管を
細くたくさん流すより、需要に応じた滑らかな配分が有利になる。各熱源は稼働させる時間帯ごとに
起動固定費がかかり、燃料費は出力に比例するため、稼働時間帯の選択(整数)と出力配分(連続)を
同時に決める必要がある。
"""

from pyscipopt import Model, quicksum

N_SRC, N_T = 2, 4
CAP = [80.0, 60.0]              # 熱源容量 [MW]
FUEL_COST = [18.0, 26.0]        # 燃料費 [$/MWh]
FIXED_COST = [400.0, 250.0]     # 期あたり起動固定費 [$]
DEMAND = [70.0, 95.0, 110.0, 60.0]  # 期別熱需要 [MWh]
LOSS_COEF = 0.0006              # 配管摩擦損失係数(流量^2に比例)


def build_model():
    model = Model("District_Heating_Grid")
    S, T = range(N_SRC), range(N_T)

    q = {(s, t): model.addVar(vtype="C", lb=0, ub=CAP[s], name=f"q_{s}_{t}") for s in S for t in T}
    on = {(s, t): model.addVar(vtype="B", name=f"on_{s}_{t}") for s in S for t in T}
    flow = {t: model.addVar(vtype="C", lb=0, name=f"flow_{t}") for t in T}
    loss = {t: model.addVar(vtype="C", lb=0, name=f"loss_{t}") for t in T}

    for s in S:
        for t in T:
            model.addCons(q[s, t] <= CAP[s] * on[s, t], f"cap_{s}_{t}")

    for t in T:
        model.addCons(flow[t] == quicksum(q[s, t] for s in S), f"flow_def_{t}")
        # 配管熱損失: 流量の2乗に比例(摩擦損失、自然な非線形)
        model.addCons(loss[t] == LOSS_COEF * flow[t] * flow[t], f"loss_def_{t}")
        model.addCons(flow[t] - loss[t] >= DEMAND[t], f"demand_{t}")

    fuel = quicksum(FUEL_COST[s] * q[s, t] for s in S for t in T)
    fixed = quicksum(FIXED_COST[s] * on[s, t] for s in S for t in T)
    model.setObjective(fuel + fixed, "minimize")

    model.data = {"q": q, "on": on, "flow": flow, "loss": loss}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
