"""鋳造チャージ配合設計（単期・複数注文の原料ブレンド） (Foundry Charge Mix)

事業ストーリー
--------------
鋳物工場の溶解係が、1回のヒート(電気炉での溶解)について、手元の複数のスクラップロット
(炭素・銅の含有率と在庫量が異なる)をどれだけ配合して溶かすか、整数のヒート回数と連続の
1回あたり装入量を決める。溶けた1つの湯は複数の注文へ配分されるため、湯の成分(濃度)は
配分先の全注文の規格窓を同時に満たす必要があり(濃度×配分量の双線形制約)、規格を満たせない
分は割高な外部購入(規格適合材の外注)で補う。これは
`foundry_charge_mix_multiperiod.py`(T1旗艦・複数期版)の単期・小規模版にあたる。
"""

from pyscipopt import Model, quicksum

N_LOT, N_ORDER = 4, 2
HEAT_MIN, HEAT_MAX = 4.0, 12.0
N_HEAT_MAX = 3

# スクラップロット: 炭素%, 銅%, 在庫[トン], 単価[$/トン]
CARBON = [0.10, 1.20, 2.50, 0.40]
COPPER = [0.05, 0.15, 0.35, 0.08]
LOT_INV = [8.0, 6.0, 5.0, 7.0]
LOT_COST = [180.0, 210.0, 240.0, 190.0]

# 注文: 炭素規格窓, 銅上限, 数量
C_LO = [0.30, 0.90]
C_HI = [0.70, 1.40]
CU_MAX = [0.18, 0.25]
QTY = [10.0, 12.0]
OUT_COST = 700.0  # 外注バックストップ単価(割高)


def build_model():
    model = Model("Foundry_Charge_Mix")
    I, O = range(N_LOT), range(N_ORDER)
    c_min, c_max = min(CARBON), max(CARBON)
    cu_min, cu_max = min(COPPER), max(COPPER)

    n_heat = model.addVar(vtype="I", lb=1, ub=N_HEAT_MAX, name="n_heat")
    heat_size = model.addVar(vtype="C", lb=0, ub=HEAT_MAX, name="heat_size")
    melt = model.addVar(vtype="C", lb=0, ub=N_HEAT_MAX * HEAT_MAX, name="melt")
    c = {i: model.addVar(vtype="C", lb=0, ub=LOT_INV[i], name=f"c_{i}") for i in I}
    cc = model.addVar(vtype="C", lb=c_min, ub=c_max, name="cc")
    cu = model.addVar(vtype="C", lb=cu_min, ub=cu_max, name="cu")
    g = {o: model.addVar(vtype="C", lb=0, ub=N_HEAT_MAX * HEAT_MAX, name=f"g_{o}") for o in O}
    out = {o: model.addVar(vtype="C", lb=0, name=f"out_{o}") for o in O}

    # ヒート回数(整数)× 1回あたり装入量(連続) = 総溶解量(双線形)
    model.addCons(melt == n_heat * heat_size, "melt_def")
    # 装入したロットの合計 = 溶解量
    model.addCons(quicksum(c[i] for i in I) == melt, "charge_mass")
    # 湯の成分(双線形: 濃度 × 溶解量 = 装入成分の質量)
    model.addCons(quicksum(CARBON[i] * c[i] for i in I) == cc * melt, "carbon_bal")
    model.addCons(quicksum(COPPER[i] * c[i] for i in I) == cu * melt, "copper_bal")
    # 湯を各注文へ配分
    model.addCons(quicksum(g[o] for o in O) == melt, "alloc")

    for o in O:
        model.addCons(cc * g[o] >= C_LO[o] * g[o], f"carb_lo_{o}")
        model.addCons(cc * g[o] <= C_HI[o] * g[o], f"carb_hi_{o}")
        model.addCons(cu * g[o] <= CU_MAX[o] * g[o], f"cu_hi_{o}")
        model.addCons(g[o] + out[o] >= QTY[o], f"qty_{o}")

    for i in I:
        model.addCons(c[i] <= LOT_INV[i], f"lot_inv_{i}")

    scrap_cost = quicksum(LOT_COST[i] * c[i] for i in I)
    outsource = quicksum(OUT_COST * out[o] for o in O)
    model.setObjective(scrap_cost + outsource, "minimize")

    model.data = {"n_heat": n_heat, "heat_size": heat_size, "c": c, "cc": cc, "cu": cu,
                  "g": g, "out": out}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Material Cost:", m.getObjVal())
