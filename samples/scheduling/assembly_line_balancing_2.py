"""アセンブリラインバランシング (Assembly Line Balancing Type-II)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Assembly_Line_Balancing_Type2")
    # 簡易定式化: タスクをステーションに配置
    x = {(t, s): model.addVar(vtype="B", name=f"x_{t}_{s}") for t in range(3) for s in range(2)}
    for t in range(3):
        model.addCons(quicksum(x[t, s] for s in range(2)) == 1, f"assign_task_{t}")
    # サイクルタイムの上限
    cycle_time = model.addVar(vtype="C", lb=0, name="cycle_time")
    TASKS = [4, 3, 5]
    for s in range(2):
        model.addCons(quicksum(x[t, s] * TASKS[t] for t in range(3)) <= cycle_time, f"cap_{s}")
    model.setObjective(cycle_time, "minimize")
    model.data = {"cycle_time": cycle_time}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cycle Time:", m.getObjVal())
