"""ガラス加工の定尺原板カット計画＋特注品寸法決定 (Glass Cutting 2D)

事業ストーリー
--------------
ガラス加工工場の生産管理担当者が、複数サイズの定尺原板(仕入先から2種類のサイズを購入可能)
から標準受注サイズの部材を何枚ずつ切り出すか(面積ベースの歩留まり制約、整数枚数)を決め、
原板の購入枚数(整数)を最小化する。あわせて、寸法自由の特注品(装飾窓など)の縦横寸法を
面積要件を満たす範囲で決める(面積=縦×横の双線形)必要があり、これは規格外の端材シートから
切り出すため専用シートの購入判断(整数)と連動する。
"""

from pyscipopt import Model, quicksum

N_ORDER = 4
SHEET_TYPES = ["small", "large"]
SHEET_AREA = {"small": 1.44, "large": 2.88}   # [m^2] (1.2x1.2, 1.2x2.4 相当)
SHEET_COST = {"small": 60.0, "large": 105.0}
UTIL_FACTOR = 0.85                             # 端材・目地ロスを考慮した実効歩留まり率

ORDER_AREA = [0.30, 0.45, 0.60, 0.20]          # 標準受注1枚あたりの面積[m^2]
ORDER_DEMAND = [20, 15, 10, 25]                # 受注枚数

CUSTOM_MIN_X, CUSTOM_MAX_X = 0.8, 2.5
CUSTOM_MIN_Y, CUSTOM_MAX_Y = 0.8, 2.0
CUSTOM_MIN_AREA = 3.0                          # 特注品の最低面積要件[m^2]
EXTRA_SHEET_AREA = 4.0
EXTRA_SHEET_COST = 130.0


def build_model():
    model = Model("Glass_Cutting_2D")
    ORD, K = range(N_ORDER), SHEET_TYPES

    nsheet = {k: model.addVar(vtype="I", lb=0, name=f"nsheet_{k}") for k in K}
    cut = {(o, k): model.addVar(vtype="I", lb=0, name=f"cut_{o}_{k}") for o in ORD for k in K}
    x = model.addVar(vtype="C", lb=CUSTOM_MIN_X, ub=CUSTOM_MAX_X, name="custom_x")
    y = model.addVar(vtype="C", lb=CUSTOM_MIN_Y, ub=CUSTOM_MAX_Y, name="custom_y")
    area_c = model.addVar(vtype="C", lb=0, name="custom_area")
    use_extra = model.addVar(vtype="B", name="use_extra_sheet")

    # 各原板タイプの面積利用: 切り出した標準部材の合計面積 <= 購入枚数 x 原板面積 x 歩留まり率
    for k in K:
        model.addCons(
            quicksum(cut[o, k] * ORDER_AREA[o] for o in ORD)
            <= nsheet[k] * SHEET_AREA[k] * UTIL_FACTOR, f"area_cap_{k}")

    # 受注充足
    for o in ORD:
        model.addCons(quicksum(cut[o, k] for k in K) >= ORDER_DEMAND[o], f"demand_{o}")

    # 特注品: 面積 = 縦 x 横(双線形)、最低面積要件、専用端材シートから切り出す
    model.addCons(area_c == x * y, "custom_area_def")
    model.addCons(area_c >= CUSTOM_MIN_AREA, "custom_min_area")
    model.addCons(area_c <= EXTRA_SHEET_AREA * use_extra, "extra_sheet_link")

    std_cost = quicksum(SHEET_COST[k] * nsheet[k] for k in K)
    extra_cost = EXTRA_SHEET_COST * use_extra
    model.setObjective(std_cost + extra_cost, "minimize")

    model.data = {"nsheet": nsheet, "cut": cut, "x": x, "y": y, "area_c": area_c,
                  "use_extra": use_extra}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Total Sheet Cost:", m.getObjVal())
