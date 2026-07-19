"""
Resource-Constrained Project Scheduling Problem (RCPSP).

This model schedules a set of project tasks under precedence and resource 
capacity constraints to minimize the total project makespan.
Reference: Pritsker, A. A. B., Watters, L. J., & Wolfe, P. M. (1969). 
Multiproject scheduling with limited resources: A zero-one programming approach. 
Management science, 16(1), 93-108.
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
            for j in jobs:
                if req[j][k] > 0:
                    for tau in range(max(0, t - duration[j] + 1), t + 1):
                        active_sum += req[j][k] * x[j, tau]
            if active_sum != 0:
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
