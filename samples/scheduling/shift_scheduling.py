"""シフトスケジューリング (Shift Scheduling Problem)

事業ストーリー
--------------
コールセンターの運営マネージャーが、1日24時間分の時間帯別必要人数(午前は少なく
夕方の問い合わせ集中時間帯に多い)を満たすよう、8時間勤務のシフトを何本・何時から
組むかを決める。シフトは1時間刻みで開始でき、開始時刻から8時間(日をまたぐ場合を
含む)にわたってその時間帯をカバーする。必要人数を割り込むとサービスレベル
(応答率)が悪化するため、各時間帯の必要人数を満たしつつ、投入するシフト本数
(=人件費)を最小化する。

各制約の業務的意味:
- **時間帯別必要人数のカバー**: 各時間帯において、その時間帯を含むシフトの
  投入本数の合計が、その時間帯に必要な最低人数以上でなければならない。
- **シフト本数最小化**: シフト本数(24時間パターンのいずれかを何本組むか)の
  合計を最小化することで、総労働時間・人件費を抑える。

(元の参考文献: Dantzig, G. B. (1954). A comment on Edie's "Traffic delays at toll booths".
Operations Research, 2(3), 339-341.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Shift_Scheduling")
    
    # Dummy data
    n_periods = 24
    periods = list(range(n_periods))
    
    demand = [10, 8, 5, 5, 8, 12, 15, 20, 25, 22, 18, 15, 18, 20, 22, 25, 28, 30, 25, 20, 15, 12, 10, 8]
    if infeasible:
        demand[0] = 500
        
    # Allowed shift patterns (start, length)
    shift_patterns = []
    for start in range(n_periods):
        shift_patterns.append((start, 8)) # 8-hour shift
        
    shifts = list(range(len(shift_patterns)))
    
    # Variables
    x = {s: model.addVar(vtype="I", lb=0, name=f"x_{s}") for s in shifts}
    
    # Objective
    model.setObjective(quicksum(x[s] for s in shifts), "minimize")
    
    # Constraints
    # Cover demand for each period
    for p in periods:
        # A shift covers this period if the period falls within [start, start + length - 1] modulo n_periods
        covering_shifts = []
        for s in shifts:
            start, length = shift_patterns[s]
            if (p - start) % n_periods < length:
                covering_shifts.append(s)
                
        model.addCons(quicksum(x[s] for s in covering_shifts) >= demand[p], name=f"demand_period_{p}")
        
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
