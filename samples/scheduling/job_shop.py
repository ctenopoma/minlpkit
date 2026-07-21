"""ジョブショップスケジューリング (Job Shop Scheduling Problem)

事業ストーリー
--------------
金属加工工場の生産管理者が、5件の受注ロット(ジョブ)を5台の機械で加工する順序を
決める。各ジョブは決まった機械の通過順(ルーティング)を持ち、機械ごとに加工時間が
異なる。同一機械では一度に1ジョブしか処理できないため、機械上での処理順を
うまく組まないと機械待ちが発生し、全ジョブの完了時刻(メイクスパン)が伸びてしまう。
機械ごとの処理順(ジョブ間の前後関係)を決めて、工場全体の生産完了を最も早くする。

各制約の業務的意味:
- **メイクスパン定義**: 各ジョブの最終工程が終わる時刻のうち最大のものが、
  工場全体の完了時刻(メイクスパン)になる。
- **ルーティング(工程順序)制約**: 各ジョブは決められた機械の順番通りにしか加工
  できない(前工程が終わってからでないと次の機械に進めない)。
- **非重複(離接)制約**: 同一機械では同時に2つのジョブを処理できないため、
  どちらのジョブを先に処理するかを二値変数で決め、後発側は先発側の終了後まで
  開始できないようにする。

なお、本モデルは各ジョブの機械経路が固定されている「古典的ジョブショップ」であり、
工程ごとに使用機械を選べる `job_shop_flexible.py`(フレキシブルジョブショップ、
機械選択の自由度がある発展版)とは前提が異なる。

(元の参考文献: Manne, A. S. (1960). On the job-shop scheduling problem.
Operations Research, 8(2), 219-223.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Job_Shop")

    # 5ジョブ x 5機械の古典的ジョブショップ
    n_jobs = 5
    n_machines = 5

    jobs = list(range(n_jobs))
    machines = list(range(n_machines))

    # Processing times: pt[job][machine]
    pt = [
        [3, 2, 2, 4, 1],
        [2, 1, 4, 3, 3],
        [4, 3, 1, 2, 2],
        [2, 4, 3, 1, 5],
        [1, 3, 2, 5, 2],
    ]

    # Routing: sequence of machines for each job
    routes = [
        [0, 1, 2, 3, 4],
        [2, 0, 1, 4, 3],
        [1, 2, 0, 3, 4],
        [3, 1, 4, 0, 2],
        [4, 3, 0, 2, 1],
    ]

    if infeasible:
        pt[0][0] = -10 # Negative processing time to cause issues or add a tight makespan bound

    M = sum(pt[j][m] for j in jobs for m in machines)

    # Variables
    # x[j, m] = start time of job j on machine m
    x = {}
    for j in jobs:
        for m in machines:
            x[j, m] = model.addVar(vtype="C", lb=0, name=f"x_{j}_{m}")

    # y[j, k, m] = 1 if job j precedes job k on machine m
    y = {}
    for j in jobs:
        for k in jobs:
            if j < k:
                for m in machines:
                    y[j, k, m] = model.addVar(vtype="B", name=f"y_{j}_{k}_{m}")

    cmax = model.addVar(vtype="C", lb=0, name="cmax")

    if infeasible:
        model.addCons(cmax <= sum(pt[0]), name="inf_cmax")

    # Objective
    model.setObjective(cmax, "minimize")

    # Constraints
    # Makespan
    for j in jobs:
        last_m = routes[j][-1]
        model.addCons(x[j, last_m] + pt[j][last_m] <= cmax, name=f"makespan_{j}")

    # Precedence (routing) constraints
    for j in jobs:
        for step in range(n_machines - 1):
            m1 = routes[j][step]
            m2 = routes[j][step+1]
            model.addCons(x[j, m2] >= x[j, m1] + pt[j][m1], name=f"route_{j}_{step}")

    # Non-overlap (disjunctive) constraints
    for j in jobs:
        for k in jobs:
            if j < k:
                for m in machines:
                    model.addCons(x[j, m] + pt[j][m] <= x[k, m] + M * (1 - y[j, k, m]), name=f"disj1_{j}_{k}_{m}")
                    model.addCons(x[k, m] + pt[k][m] <= x[j, m] + M * y[j, k, m], name=f"disj2_{j}_{k}_{m}")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())
    else:
        print("No optimal solution found.")

if __name__ == "__main__":
    main()
