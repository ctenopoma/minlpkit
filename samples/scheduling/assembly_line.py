"""組立ラインバランシング (Assembly Line Balancing Problem)

事業ストーリー
--------------
家電メーカーの生産技術者が、新製品の組立ラインを設計する。1台の製品を完成させる
までに必要な12の組立タスク(配線・ねじ締め・検査など)を、複数の作業ステーション
(作業員1人分の持ち場)に割り当てる。タスクには「この部品を取り付ける前に土台を
組んでおく必要がある」といった前後関係があり、また各ステーションの作業時間が
タクトタイム(1台あたりに許される最大サイクルタイム)を超えてはならない。使用する
ステーション数=配置する作業員数そのものなので、これを最小化することが人件費削減
に直結する。

各制約の業務的意味:
- **タスクの一意割当**: 各組立タスクはちょうど1つのステーションで実施される
  (重複や漏れがあってはならない)。
- **サイクルタイム制約**: 1ステーションに割り当てたタスクの合計所要時間は、
  タクトタイム(ラインの稼働速度で決まる上限)を超えられない。
- **前後関係制約**: 部品の組立順序上、先行タスクは後続タスクと同じか、より上流
  (番号の小さい)ステーションで処理されなければならない。
- **ステーション使用順の整列**: 対称性除去のため、ステーションは若い番号から
  順に使う(k番目を使わずにk+1番目だけ使う、という無駄な配置を排除する)。
- **ステーション数最小化**: 稼働させるステーション数(=配置人員数)を最小化し、
  ライン運用コストを抑える。

(元の学術的定義: Salveson (1955) - The Assembly Line Balancing Problem)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("AssemblyLine")

    # 12タスクからなる組立工程(前後関係付き)
    tasks = list(range(1, 13))
    durations = {1: 4, 2: 3, 3: 5, 4: 2, 5: 6, 6: 3,
                 7: 4, 8: 5, 9: 2, 10: 6, 11: 3, 12: 4}
    precedences = [
        (1, 2), (1, 3), (2, 4), (3, 5), (4, 6), (5, 6),
        (6, 7), (7, 8), (7, 9), (8, 10), (9, 10), (10, 11), (11, 12),
    ]
    cycle_time = 15
    max_stations = 6

    # Variables
    x = {} # x[i, k] = 1 if task i is assigned to station k
    y = {} # y[k] = 1 if station k is used
    for i in tasks:
        for k in range(max_stations):
            x[i, k] = model.addVar(vtype="B", name=f"assign_{i}_{k}")
    for k in range(max_stations):
        y[k] = model.addVar(vtype="B", name=f"use_station_{k}")

    # Constraints
    # Each task assigned to exactly one station
    for i in tasks:
        model.addCons(quicksum(x[i, k] for k in range(max_stations)) == 1, name=f"one_station_{i}")

    # Cycle time constraint
    for k in range(max_stations):
        model.addCons(quicksum(durations[i] * x[i, k] for i in tasks) <= cycle_time * y[k], name=f"cycle_time_{k}")

    # Precedence constraints
    for (i, j) in precedences:
        # Station of i must be <= station of j
        model.addCons(
            quicksum(k * x[i, k] for k in range(max_stations)) <= quicksum(k * x[j, k] for k in range(max_stations)),
            name=f"prec_{i}_{j}"
        )

    # Station ordering
    for k in range(max_stations - 1):
        model.addCons(y[k] >= y[k+1], name=f"station_order_{k}")

    if infeasible:
        model.addCons(quicksum(y[k] for k in range(max_stations)) == 0, name="inf_constraint")

    # Objective
    model.setObjective(quicksum(y[k] for k in range(max_stations)), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
