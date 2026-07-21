"""資源制約付きプロジェクトスケジューリング (Resource-Constrained Project Scheduling Problem, RCPSP)

事業ストーリー
--------------
建設・プラント工事の現場所長が、複数の作業(基礎工事・配管・電気工事など)からなる
プロジェクトの着工日程を決める。各作業には「配管工事は基礎工事が終わってから」
といった前後関係があり、さらにクレーンや作業員チームなど台数・人数に限りのある
資源を複数の作業が奪い合う。資源の取り合いで作業が同時に進められない場合は
開始を遅らせる必要があり、前後関係と資源制約の両方を満たしながらプロジェクト
全体の完了(メイクスパン)を最短化する。

各制約の業務的意味:
- **開始時刻の一意性**: 各作業はちょうど1つの時刻に開始する(分割不可・重複開始
  不可)。
- **前後関係制約**: 後続作業は先行作業の完了(開始時刻+所要時間)を待ってからしか
  開始できない。
- **資源容量制約**: クレーンや作業員チームなど、各時刻に同時稼働している作業の
  資源使用量の合計が、保有する資源の台数・人数の上限を超えてはならない。
- **メイクスパン最小化**: プロジェクト全体を表すダミー終了タスクの開始時刻
  (=全作業完了時刻)を最小化する。

(元の参考文献: Pritsker, A. A. B., Watters, L. J., & Wolfe, P. M. (1969).
Multiproject scheduling with limited resources: A zero-one programming approach.
Management science, 16(1), 93-108.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("RCPSP")
    
    n_jobs = 6
    jobs = list(range(n_jobs)) # 0 and 5 are dummy start/end
    
    duration = {0: 0, 1: 3, 2: 4, 3: 2, 4: 5, 5: 0}
    
    # Precedence relations
    precedences = [(0, 1), (0, 2), (1, 3), (2, 3), (2, 4), (3, 5), (4, 5)]
    
    resources = [1, 2]
    capacity = {1: 4, 2: 3}
    
    req = {
        1: {1: 2, 2: 1},
        2: {1: 1, 2: 2},
        3: {1: 2, 2: 0},
        4: {1: 1, 2: 1}
    }
    for j in [0, 5]:
        req[j] = {1: 0, 2: 0}
        
    if infeasible:
        req[1][1] = 10 # More than capacity
        
    T = sum(duration.values())
    time_periods = list(range(T))
    
    # x[j, t] = 1 if job j starts at time t
    x = {}
    for j in jobs:
        for t in time_periods:
            x[j, t] = model.addVar(vtype="B", name=f"x_{j}_{t}")
            
    # Objective
    model.setObjective(quicksum(t * x[n_jobs-1, t] for t in time_periods), "minimize")
    
    # Constraints
    # Each job starts exactly once
    for j in jobs:
        model.addCons(quicksum(x[j, t] for t in time_periods) == 1, name=f"start_once_{j}")
        
    # Precedence
    for (i, j) in precedences:
        start_i = quicksum(t * x[i, t] for t in time_periods)
        start_j = quicksum(t * x[j, t] for t in time_periods)
        model.addCons(start_j >= start_i + duration[i], name=f"prec_{i}_{j}")
        
    # Resource constraints
    for k in resources:
        for t in time_periods:
            # Active jobs at time t
            active_sum = 0
            has_terms = False
            for j in jobs:
                if req[j][k] > 0:
                    for tau in range(max(0, t - duration[j] + 1), t + 1):
                        active_sum += req[j][k] * x[j, tau]
                        has_terms = True
            if has_terms:
                model.addCons(active_sum <= capacity[k], name=f"res_{k}_{t}")
                
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
