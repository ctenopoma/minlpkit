"""セメントミル夜間操業スケジュール (Cement Mill Scheduling)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Cement_Mill_Scheduling")
    T = 6
    run = {t: model.addVar(vtype="B", name=f"run_{t}") for t in range(T)}
    # ピーク時(t=2, 3)は停止
    model.addCons(run[2] == 0)
    model.addCons(run[3] == 0)
    # 総生産時間確保
    model.addCons(quicksum(run[t] for t in range(T)) >= 3)
    model.setObjective(quicksum(run[t] * 10 for t in range(T)), "minimize")
    model.data = {"run": run}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Cost:", m.getObjVal())
