"""調達契約オプション選定 (Supply Contract Selection)

調達部門のバイヤーが、複数のサプライヤーが提示する契約オプション(固定価格契約・
数量割引契約・スポット契約など)の中から、複数の資材品目についてどの契約をどれだけ
使うかを決める意思決定である。各契約には最低発注量(結んだら一定量以上を買う義務)と
上限があり、品目ごとの需要を満たしつつ総コストを最小化する。契約を結ぶかどうかの
0-1判断(固定費・最低発注量が発生するか)と発注量の連続決定が結合するため、
「どの契約を使うか」自体が組合せ的な意思決定になる。
"""

from pyscipopt import Model, quicksum

ITEMS = ["Resin", "Steel"]
CONTRACTS = ["A", "B", "C"]

demand = {"Resin": 120.0, "Steel": 90.0}
# 契約ごとの単価・固定費・最低発注量・上限(品目非依存の簡略設定)
unit_price = {"A": 12.0, "B": 9.5, "C": 11.0}
fixed_fee = {"A": 0.0, "B": 400.0, "C": 150.0}
min_order = {"A": 0.0, "B": 60.0, "C": 20.0}
max_order = {"A": 200.0, "B": 200.0, "C": 80.0}


def build_model():
    model = Model("Supply_Contract_Selection")

    use = {c: model.addVar(vtype="B", name=f"use_{c}") for c in CONTRACTS}
    qty = {(i, c): model.addVar(vtype="C", lb=0, name=f"qty_{i}_{c}") for i in ITEMS for c in CONTRACTS}

    for i in ITEMS:
        model.addCons(quicksum(qty[i, c] for c in CONTRACTS) == demand[i], name=f"meet_demand_{i}")

    for c in CONTRACTS:
        total_c = quicksum(qty[i, c] for i in ITEMS)
        # 契約を使わなければ発注ゼロ、使うなら最低発注量以上・上限以下
        model.addCons(total_c >= min_order[c] * use[c], name=f"min_order_{c}")
        model.addCons(total_c <= max_order[c] * use[c], name=f"max_order_{c}")

    model.setObjective(
        quicksum(unit_price[c] * qty[i, c] for i in ITEMS for c in CONTRACTS)
        + quicksum(fixed_fee[c] * use[c] for c in CONTRACTS),
        "minimize",
    )
    model.data = {"use": use, "qty": qty}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Contract Cost:", m.getObjVal())
