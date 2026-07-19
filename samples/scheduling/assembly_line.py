"""
Assembly Line Balancing Problem

This model assigns tasks to workstations such that precedence constraints are respected
and the number of workstations (or cycle time) is minimized.
Relevant concept: Salveson (1955) - The Assembly Line Balancing Problem.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("AssemblyLine")
    
    # Dummy data
    tasks = [1, 2, 3, 4, 5]
    durations = {1: 4, 2: 3, 3: 5, 4: 2, 5: 6}
    precedences = [(1, 2), (1, 3), (2, 4), (3, 5), (4, 5)]
    cycle_time = 10
    max_stations = 5
    
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
