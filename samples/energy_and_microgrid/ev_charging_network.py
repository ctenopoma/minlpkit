"""都市EV急速充電ネットワーク設計 (EV Charging Network Design)

事業ストーリー
--------------
都市インフラ計画部門の担当者が、候補地に急速充電器を「設置するか」だけでなく「何基設置するか」
(整数のロット決定)を決め、各エリアの充電需要を、候補地からの距離で決まるカバー可能圏内の
充電器容量でまかなう。充電器の基数はエリア需要に対する供給容量を決めるため、開設判断(整数≥1か)
と基数(整数)がリンクし、さらに各候補地がどのエリアにどれだけ供給するかという配分(連続)を
同時に決める必要がある。
"""

from pyscipopt import Model, quicksum

LOCS = ["Downtown", "Airport", "Suburb_N", "Suburb_S"]
ZONES = ["Z1", "Z2", "Z3", "Z4"]

# 候補地がカバーできるエリア(距離圏内かどうか)
COVERAGE = {
    ("Downtown", "Z1"): 1, ("Downtown", "Z2"): 1, ("Downtown", "Z3"): 0, ("Downtown", "Z4"): 0,
    ("Airport", "Z2"): 1, ("Airport", "Z3"): 1, ("Airport", "Z1"): 0, ("Airport", "Z4"): 0,
    ("Suburb_N", "Z3"): 1, ("Suburb_N", "Z4"): 1, ("Suburb_N", "Z1"): 0, ("Suburb_N", "Z2"): 0,
    ("Suburb_S", "Z4"): 1, ("Suburb_S", "Z1"): 1, ("Suburb_S", "Z2"): 0, ("Suburb_S", "Z3"): 0,
}
CAP_PER_CHARGER = 40.0     # 充電器1基あたりの1日供給可能台数
MAX_CHARGERS = 6           # 候補地あたり最大基数
FIXED_COST = 50000.0       # 候補地を開設する固定費
UNIT_COST = 12000.0        # 充電器1基あたり設置費
DEMAND = {"Z1": 90.0, "Z2": 70.0, "Z3": 110.0, "Z4": 60.0}


def build_model():
    model = Model("EV_Charging_Network")
    L, Z = LOCS, ZONES

    open_st = {l: model.addVar(vtype="B", name=f"open_{l}") for l in L}
    n_charger = {l: model.addVar(vtype="I", lb=0, ub=MAX_CHARGERS, name=f"n_{l}") for l in L}
    alloc = {(l, z): model.addVar(vtype="C", lb=0, name=f"alloc_{l}_{z}")
             for l in L for z in Z if COVERAGE.get((l, z), 0) == 1}

    for l in L:
        model.addCons(quicksum(alloc[l, z] for z in Z if (l, z) in alloc)
                      <= CAP_PER_CHARGER * n_charger[l], f"supply_cap_{l}")
        # 開設していない候補地には充電器を置けない/逆に基数>0なら開設扱い
        model.addCons(n_charger[l] <= MAX_CHARGERS * open_st[l], f"open_link_{l}")

    for z in Z:
        model.addCons(quicksum(alloc[l, z] for l in L if (l, z) in alloc) >= DEMAND[z],
                      f"demand_{z}")

    fixed = quicksum(FIXED_COST * open_st[l] for l in L)
    unit = quicksum(UNIT_COST * n_charger[l] for l in L)
    model.setObjective(fixed + unit, "minimize")

    model.data = {"open_st": open_st, "n_charger": n_charger, "alloc": alloc}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Setup Cost:", m.getObjVal())
