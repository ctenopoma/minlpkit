"""航空便オーバーブッキング・収益管理 (Airline Overbooking Control)

事業ストーリー
--------------
航空会社の収益管理(レベニューマネジメント)部門が、複数便・複数運賃クラス(ビジネス/
エコノミー)について、ノーショー(無連絡不搭乗)を見込んだ許容予約数を決める。
予約を座席数より多く受け付けるほど期待収益は増えるが、実際の搭乗希望者が座席数を
超えた場合はデナイドボーディング(搭乗拒否)補償金という高コストが発生する。

各制約の業務的意味:
- **クラス別需要上限**: 各便・各クラスで受け付けられる予約数は市場需要で頭打ちになる。
- **期待搭乗者数による座席容量制約**: ノーショー率を見込んだ期待搭乗者数(予約数×
  搭乗率)が物理座席数を超えないようにする(超過はリスク許容度の範囲内)。
- **オーバーブッキング枠の二値選択**: 各便で「保守的運用」と「積極的オーバーブッキング」
  のどちらの方針を取るかを二値変数で決める。積極運用を選ぶと許容予約数の上限が
  引き上がる代わりに、デナイドボーディングの期待コスト率が上がる(高リスク・高リターン)。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

FLIGHTS = ["FL101", "FL205", "FL318"]
CLASSES = ["business", "economy"]

CAPACITY = {"FL101": 150, "FL205": 180, "FL318": 130}
SHOW_RATE = {"business": 0.95, "economy": 0.82}   # ノーショー率を除いた搭乗率
FARE = {"business": 480, "economy": 165}
DEMAND = {
    ("FL101", "business"): 30, ("FL101", "economy"): 160,
    ("FL205", "business"): 35, ("FL205", "economy"): 190,
    ("FL318", "business"): 22, ("FL318", "economy"): 140,
}
# 保守的/積極的オーバーブッキング方針でのデナイドボーディング期待コスト率($/期待超過1席)
BUMP_COST_CONSERVATIVE = 40
BUMP_COST_AGGRESSIVE = 90
OVERBOOK_EXTRA = 0.12   # 積極方針を選ぶと座席容量制約をこの割合まで緩める


def build_model():
    model = Model("Airline_Overbooking")

    bk = {(f, c): model.addVar(vtype="I", lb=0, ub=DEMAND[f, c], name=f"bk_{f}_{c}")
          for f in FLIGHTS for c in CLASSES}
    aggressive = {f: model.addVar(vtype="B", name=f"aggr_{f}") for f in FLIGHTS}
    # 期待搭乗者数(補助変数として明示化: 二値×連続の積を避けるための線形化に使う)
    expected_board = {f: model.addVar(vtype="C", lb=0, name=f"eb_{f}") for f in FLIGHTS}
    # 方針ごとのデナイドボーディング期待コスト(big-M線形化で「選んだ方針の単価」だけが効く)
    bump = {f: model.addVar(vtype="C", lb=0, name=f"bump_{f}") for f in FLIGHTS}

    rate_low = 0.05 * BUMP_COST_CONSERVATIVE
    rate_high = 0.05 * BUMP_COST_AGGRESSIVE
    big_m = rate_high * max(CAPACITY.values()) * 1.3

    for f in FLIGHTS:
        model.addCons(
            expected_board[f] == quicksum(SHOW_RATE[c] * bk[f, c] for c in CLASSES),
            f"expected_board_{f}")
        cap_limit = CAPACITY[f] * (1 + OVERBOOK_EXTRA * aggressive[f])
        model.addCons(expected_board[f] <= cap_limit, f"capacity_{f}")
        # aggressive[f]=0 のとき下段が有効(低コスト率)、=1 のとき上段が有効(高コスト率)
        model.addCons(bump[f] >= rate_low * expected_board[f] - big_m * aggressive[f],
                       f"bump_low_{f}")
        model.addCons(bump[f] >= rate_high * expected_board[f] - big_m * (1 - aggressive[f]),
                       f"bump_high_{f}")

    revenue = quicksum(FARE[c] * bk[f, c] for f in FLIGHTS for c in CLASSES)
    bump_cost = quicksum(bump[f] for f in FLIGHTS)
    model.setObjective(revenue - bump_cost, "maximize")
    model.data = {"bk": bk, "aggressive": aggressive, "bump": bump}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Revenue:", m.getObjVal())
