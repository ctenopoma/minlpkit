"""倉庫スロッティング配置最適化 (Warehouse Slotting Optimization)

倉庫運営マネージャーが、複数のSKU(在庫管理単位)をピッキング効率の異なる複数のスロット
(棚位置)へ割り当てる意思決定である。出荷頻度の高いSKUを入出庫口に近い高効率スロットへ
配置するほどピッキング時間が短縮される一方、各スロットは体積上限を持つためSKUの物理サイズ
に応じて収容できる品目数が制限される。1つのスロットに複数SKUを混載してよいが、
容量を超えてはならないというナップサック型の制約と、SKUごとに1か所にしか配置できない
という割当制約が組み合わさり、単純な一対一マッチングより現実的な配置問題になる。
"""

from pyscipopt import Model, quicksum

ITEMS = ["Item1", "Item2", "Item3", "Item4", "Item5"]
SLOTS = ["SlotA", "SlotB", "SlotC"]

item_volume = {"Item1": 4, "Item2": 3, "Item3": 5, "Item4": 2, "Item5": 6}
slot_capacity = {"SlotA": 8, "SlotB": 7, "SlotC": 9}
# 効率スコア = 出荷頻度 × スロットの近接度(値が大きいほど良い)
pick_efficiency = {
    ("Item1", "SlotA"): 18, ("Item1", "SlotB"): 12, ("Item1", "SlotC"): 8,
    ("Item2", "SlotA"): 10, ("Item2", "SlotB"): 15, ("Item2", "SlotC"): 9,
    ("Item3", "SlotA"): 8,  ("Item3", "SlotB"): 9,  ("Item3", "SlotC"): 16,
    ("Item4", "SlotA"): 14, ("Item4", "SlotB"): 11, ("Item4", "SlotC"): 7,
    ("Item5", "SlotA"): 6,  ("Item5", "SlotB"): 13, ("Item5", "SlotC"): 12,
}


def build_model():
    model = Model("Warehouse_Slotting")

    x = {(i, s): model.addVar(vtype="B", name=f"x_{i}_{s}") for i in ITEMS for s in SLOTS}

    for i in ITEMS:
        model.addCons(quicksum(x[i, s] for s in SLOTS) == 1, name=f"assign_item_{i}")

    for s in SLOTS:
        # 複数SKUを混載可能だが体積上限を守る(ナップサック制約)
        model.addCons(quicksum(item_volume[i] * x[i, s] for i in ITEMS) <= slot_capacity[s],
                       name=f"volume_cap_{s}")

    model.setObjective(quicksum(x[i, s] * pick_efficiency[i, s] for i in ITEMS for s in SLOTS), "maximize")
    model.data = {"x": x}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Value:", m.getObjVal())
