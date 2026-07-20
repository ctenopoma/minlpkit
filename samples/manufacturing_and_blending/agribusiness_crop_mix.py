"""農業法人の作付計画 (Agribusiness Crop Mix Planning)

事業ストーリー
--------------
農業法人の営農計画担当者が、来季どの作物をどの圃場にどれだけ作付けするかを決める。
作物ごとに単位面積あたりの利益・水使用量・労働時間が異なり、圃場ごとに利用可能面積が
異なる(圃場1は灌漑設備あり、圃場2は天水のみ、など)。

各制約の業務的意味:
- **圃場ごとの面積上限**: 各圃場は物理的な面積制約を持ち、複数作物で分け合う。
- **総水資源制約**: 灌漑用水は地域全体で上限があり、全圃場・全作物の水使用量合計が
  それを超えてはならない。
- **労働力制約**: 収穫期の作業員シフトは有限で、作物ごとの労働時間原単位が異なる。
- **作付ロット下限(整数決定)**: 種苗・農機の段取り上、ある作物を作付けるなら
  最低作付面積(ロット)を超えないと採算が合わない。作付するかしないかの二値決定
  `plant[c]` と、作付けするなら最低面積以上という条件(semi-continuous)を課す。
- **作物多様化(リスク分散)**: 単一作物への集中は天候・市況リスクを高めるため、
  作付する作物数の下限を課す(輪作・分散栽培の実務要件)。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

CROPS = ["wheat", "corn", "soy", "barley", "canola"]
FIELDS = ["field_irrigated", "field_rainfed"]

# 作物ごとの単位利益($/ha)・水使用量(千L/ha)・労働時間(h/ha)
PROFIT = {"wheat": 420, "corn": 610, "soy": 500, "barley": 360, "canola": 470}
WATER = {"wheat": 1.4, "corn": 2.0, "soy": 1.7, "barley": 1.1, "canola": 1.6}
LABOR = {"wheat": 3.0, "corn": 4.5, "soy": 3.8, "barley": 2.6, "canola": 3.4}

FIELD_AREA = {"field_irrigated": 260.0, "field_rainfed": 340.0}
TOTAL_WATER = 650.0       # 千L、地域の灌漑用水割当上限
TOTAL_LABOR = 1800.0      # h、収穫期の総労働力
MIN_LOT = 15.0            # ha、作付するなら最低この面積
MIN_CROPS = 3             # 作付する作物種数の下限(分散栽培要件)


def build_model():
    model = Model("Agribusiness_Crop_Mix")

    area = {(c, f): model.addVar(vtype="C", lb=0, name=f"area_{c}_{f}")
            for c in CROPS for f in FIELDS}
    plant = {c: model.addVar(vtype="B", name=f"plant_{c}") for c in CROPS}

    for f in FIELDS:
        model.addCons(quicksum(area[c, f] for c in CROPS) <= FIELD_AREA[f],
                       f"field_cap_{f}")

    model.addCons(
        quicksum(WATER[c] * area[c, f] for c in CROPS for f in FIELDS) <= TOTAL_WATER,
        "water_budget")
    model.addCons(
        quicksum(LABOR[c] * area[c, f] for c in CROPS for f in FIELDS) <= TOTAL_LABOR,
        "labor_budget")

    total_area_max = sum(FIELD_AREA.values())
    for c in CROPS:
        total_c = quicksum(area[c, f] for f in FIELDS)
        model.addCons(total_c <= total_area_max * plant[c], f"lot_upper_{c}")
        model.addCons(total_c >= MIN_LOT * plant[c], f"lot_lower_{c}")

    model.addCons(quicksum(plant[c] for c in CROPS) >= MIN_CROPS, "min_diversification")

    model.setObjective(
        quicksum(PROFIT[c] * area[c, f] for c in CROPS for f in FIELDS), "maximize")
    model.data = {"area": area, "plant": plant}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Total Profit:", m.getObjVal())
