"""
Job Shop Scheduling Problem.

This model schedules a set of multi-operation jobs on a set of machines 
to minimize the makespan, where each job has a specific sequence of machines.
Reference: Manne, A. S. (1960). On the job-shop scheduling problem. 
Operations Research, 8(2), 219-223.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Job_Shop")
    
    # Dummy data
    n_jobs = 3
    n_machines = 3
    
    jobs = list(range(n_jobs))
    machines = list(range(n_machines))
    
    # Processing times: pt[job][machine]
    pt = [
        [3, 2, 2],
        [2, 1, 4],
        [4, 3, 1]
    ]
    
    # Routing: sequence of machines for each job
    routes = [
        [0, 1, 2],
        [2, 0, 1],
        [1, 2, 0]
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
