"""送電線拡張計画 (Transmission Expansion Planning, 簡易版)

送配電事業者の系統計画担当者が、複数の候補送電線候補の中から新設するコリドーを選び、
新設後の系統で複数の需要期(平常期・ピーク期)それぞれの潮流(送電量)を決める意思決定
である。線を建設するかどうかは巨額の投資を伴う0-1判断であり、建設した線にしか潮流を
流せない(容量制約が建設可否に連動するdisjunctive構造)。需要期ごとに必要な送電量が
異なるため、ある需要期では不要でも別の需要期のピークを賄うために建設が必要になる場合が
あり、単一シナリオでは見えない投資の必要性を複数期間で捉える。
"""

from pyscipopt import Model, quicksum

LINES = ["L1", "L2", "L3"]
PERIODS = ["normal", "peak"]

build_cost = {"L1": 1000.0, "L2": 1400.0, "L3": 900.0}
line_capacity = {"L1": 50.0, "L2": 70.0, "L3": 40.0}
flow_cost = {"L1": 2.0, "L2": 1.5, "L3": 2.5}
demand = {"normal": 60.0, "peak": 95.0}


def build_model():
    model = Model("Transmission_Expansion")

    build = {l: model.addVar(vtype="B", name=f"build_{l}") for l in LINES}
    flow = {(l, p): model.addVar(vtype="C", lb=0, ub=line_capacity[l], name=f"flow_{l}_{p}")
            for l in LINES for p in PERIODS}

    for l in LINES:
        for p in PERIODS:
            # 建設していない線には潮流を流せない
            model.addCons(flow[l, p] <= line_capacity[l] * build[l], name=f"capacity_{l}_{p}")

    for p in PERIODS:
        model.addCons(quicksum(flow[l, p] for l in LINES) >= demand[p], name=f"demand_{p}")

    model.setObjective(
        quicksum(build_cost[l] * build[l] for l in LINES)
        + quicksum(flow_cost[l] * flow[l, p] for l in LINES for p in PERIODS),
        "minimize",
    )
    model.data = {"build": build, "flow": flow}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Cost:", m.getObjVal())
