"""容量制約付き複数期施設配置問題 (Capacitated Facility Location)

事業ストーリー
--------------
サプライチェーン計画担当者が、需要が季節的に変動する複数期間を見据えて、どの倉庫拠点を
開設するか(整数の開設判断、一度開けば全期間使える固定資産)と、開設後の各期において
各拠点からどの顧客へどれだけ供給するかを同時に決める。拠点の開設は一度きりの投資判断だが、
容量制約と需要充足は期ごとに独立して効くため、需要が繁忙期に偏っている場合はピーク期の
需要を満たせるだけの拠点網を用意しておく必要がある(時間結合)。
"""

from pyscipopt import Model, quicksum

FACILITIES = ["F1", "F2", "F3"]
CUSTOMERS = ["C1", "C2", "C3", "C4"]
PERIODS = ["low_season", "peak_season"]

CAP = {"F1": 120, "F2": 90, "F3": 100}
FIXED_COST = {"F1": 8000, "F2": 6000, "F3": 7000}
SHIP_COST = 2.0
DEMAND = {
    ("C1", "low_season"): 20, ("C1", "peak_season"): 35,
    ("C2", "low_season"): 25, ("C2", "peak_season"): 45,
    ("C3", "low_season"): 15, ("C3", "peak_season"): 30,
    ("C4", "low_season"): 20, ("C4", "peak_season"): 40,
}


def build_model():
    model = Model("Capacitated_Facility_Location")
    F, C, T = FACILITIES, CUSTOMERS, PERIODS

    y = {f: model.addVar(vtype="B", name=f"y_{f}") for f in F}
    x = {(f, c, t): model.addVar(vtype="C", lb=0, name=f"x_{f}_{c}_{t}")
         for f in F for c in C for t in T}

    for c in C:
        for t in T:
            model.addCons(quicksum(x[f, c, t] for f in F) >= DEMAND[c, t], f"demand_{c}_{t}")
    for f in F:
        for t in T:
            model.addCons(quicksum(x[f, c, t] for c in C) <= CAP[f] * y[f], f"cap_{f}_{t}")

    fixed = quicksum(FIXED_COST[f] * y[f] for f in F)
    ship = quicksum(SHIP_COST * x[f, c, t] for f in F for c in C for t in T)
    model.setObjective(fixed + ship, "minimize")

    model.data = {"x": x, "y": y}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
