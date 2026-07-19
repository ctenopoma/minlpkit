"""倉庫スロッティング配置最適化 (Warehouse Slotting Optimization)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Warehouse_Slotting")
    ITEMS = ["Item1", "Item2"]; SLOTS = ["SlotA", "SlotB"]
    x = {(i, s): model.addVar(vtype="B", name=f"x_{i}_{s}") for i in ITEMS for s in SLOTS}
    for i in ITEMS:
        model.addCons(quicksum(x[i, s] for s in SLOTS) == 1, f"assign_item_{i}")
    for s in SLOTS:
        model.addCons(quicksum(x[i, s] for i in ITEMS) <= 1, f"assign_slot_{s}")
    model.setObjective(quicksum(x[i, s] * 10 for i in ITEMS for s in SLOTS), "maximize")
    model.data = {"x": x}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Value:", m.getObjVal())
