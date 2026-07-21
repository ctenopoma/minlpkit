"""アセンブリラインバランシング Type-II (Assembly Line Balancing)

事業ストーリー
--------------
製造ラインの工程設計担当者(インダストリアルエンジニア)が、既に決まっているステーション数
(設備投資済み)のもとで、各作業タスクをどのステーションに割り当てればサイクルタイム
(1台あたりの生産に要する最長ステーション時間)を最小化できるかを決める。
Type-II ALB(ステーション数固定・サイクルタイム最小化)は、増産・平準化のたびに
現場で繰り返し解かれる典型的な工程再設計問題である。

各制約の業務的意味:
- **各タスクはちょうど1ステーションに割当**: 作業の重複も欠落も許されない。
- **先行関係(precedence)**: 車体組立の物理的順序(例:配線後でないと内装パネルを
  取り付けられない)により、あるタスクは先行タスクと同じか後のステーションでしか
  実行できない(タスク番号順に並ぶステーション制約)。
- **サイクルタイムは全ステーションの作業時間合計の最大値**: ボトルネックとなる
  ステーションの負荷がライン全体の生産速度を決める(直列ラインの本質)。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

N_TASKS = 8
N_STATIONS = 3
TASK_TIME = [4, 3, 5, 2, 6, 3, 4, 5]     # 各タスクの標準作業時間(秒)
# 先行関係: (a, b) は「タスクaはタスクbより前(同ステーション以下の番号)で完了」
PRECEDENCE = [(0, 2), (1, 2), (2, 4), (3, 4), (4, 6), (5, 6), (6, 7)]


def build_model():
    model = Model("Assembly_Line_Balancing_Type2")

    x = {(t, s): model.addVar(vtype="B", name=f"x_{t}_{s}")
         for t in range(N_TASKS) for s in range(N_STATIONS)}
    cycle_time = model.addVar(vtype="C", lb=0, name="cycle_time")

    for t in range(N_TASKS):
        model.addCons(quicksum(x[t, s] for s in range(N_STATIONS)) == 1,
                       f"assign_task_{t}")

    for s in range(N_STATIONS):
        model.addCons(
            quicksum(x[t, s] * TASK_TIME[t] for t in range(N_TASKS)) <= cycle_time,
            f"cap_{s}")

    # 先行タスクaの所属ステーション番号 <= 後続タスクbの所属ステーション番号
    station_index = {t: quicksum(s * x[t, s] for s in range(N_STATIONS))
                      for t in range(N_TASKS)}
    for a, b in PRECEDENCE:
        model.addCons(station_index[a] <= station_index[b], f"prec_{a}_{b}")

    model.setObjective(cycle_time, "minimize")
    model.data = {"x": x, "cycle_time": cycle_time}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Cycle Time:", m.getObjVal())
