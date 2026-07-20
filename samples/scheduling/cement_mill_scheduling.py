"""セメントミル操業スケジュール (Cement Mill Scheduling)

事業ストーリー
--------------
セメント工場のエネルギー管理担当者が、2基あるミル(粉砕設備)の稼働スケジュールを
決める。電力は時間帯別料金(ピーク時は高額)であり、ピーク時間帯は極力停止したいが、
一定の生産量は日々確保する必要がある。ミルは起動のたびに大きな起動電力(スパイク)を
要するため、頻繁なオンオフはコスト増につながる。

各制約の業務的意味:
- **ピーク時間帯の稼働禁止**: 電力需給ひっ迫時間帯は契約上・コスト上、大型ミルの
  稼働を避ける必要がある。
- **日次生産量の下限**: 2基合計の稼働時間が、その日の出荷計画を満たす最低時間数を
  下回ってはならない。
- **起動検知(二値変数)**: 停止状態から稼働状態に切り替わった時間帯では起動フラグが
  立ち、起動コスト(電力スパイク・機械摩耗)が加算される。これにより「こまめに
  オンオフ」よりも「まとめて稼働」が自然と有利になる。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

MILLS = ["mill_1", "mill_2"]
N_HOURS = 6
PEAK_HOURS = {2, 3}          # この時間帯は稼働禁止(電力ピーク)
RUN_COST = {"mill_1": 10, "mill_2": 14}
STARTUP_COST = {"mill_1": 25, "mill_2": 35}
MIN_TOTAL_RUN_HOURS = 6      # 2基合計での最低稼働時間数(日次出荷量を満たすため)


def build_model():
    model = Model("Cement_Mill_Scheduling")

    run = {(m, t): model.addVar(vtype="B", name=f"run_{m}_{t}")
           for m in MILLS for t in range(N_HOURS)}
    startup = {(m, t): model.addVar(vtype="B", name=f"su_{m}_{t}")
               for m in MILLS for t in range(1, N_HOURS)}

    for m in MILLS:
        for t in PEAK_HOURS:
            model.addCons(run[m, t] == 0, f"peak_off_{m}_{t}")
        for t in range(1, N_HOURS):
            model.addCons(startup[m, t] >= run[m, t] - run[m, t - 1], f"startup_{m}_{t}")

    model.addCons(
        quicksum(run[m, t] for m in MILLS for t in range(N_HOURS)) >= MIN_TOTAL_RUN_HOURS,
        "min_production")

    run_cost = quicksum(RUN_COST[m] * run[m, t] for m in MILLS for t in range(N_HOURS))
    startup_cost = quicksum(STARTUP_COST[m] * startup[m, t]
                             for m in MILLS for t in range(1, N_HOURS))
    model.setObjective(run_cost + startup_cost, "minimize")
    model.data = {"run": run, "startup": startup}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Total Operating Cost:", m.getObjVal())
