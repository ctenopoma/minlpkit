"""
Fixed Charge Network Flow Problem.
This model minimizes the total cost of routing flow through a network, where 
using a directed edge incurs a fixed cost in addition to a variable per-unit cost.
Reference: Magnanti, T. L., & Wong, R. T. (1984). Network design and transportation planning: Models and algorithms. Transportation science.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("FixedChargeNetwork")
    
    nodes = [1, 2, 3, 4]
    edges = [(1, 2), (1, 3), (2, 3), (2, 4), (3, 4)]
    
    fixed_cost = {(1, 2): 10, (1, 3): 15, (2, 3): 5, (2, 4): 10, (3, 4): 12}
    variable_cost = {(1, 2): 2, (1, 3): 3, (2, 3): 1, (2, 4): 4, (3, 4): 2}
    capacity = {(1, 2): 10, (1, 3): 10, (2, 3): 5, (2, 4): 10, (3, 4): 10}
    
    if infeasible:
        supply = {1: 30, 2: 0, 3: 0, 4: -30} # Exceeds capacity
    else:
        supply = {1: 15, 2: 0, 3: 0, 4: -15}
        
    x = {}
    y = {}
    
    for i, j in edges:
        x[i, j] = model.addVar(vtype="C", name=f"flow_{i}_{j}", lb=0)
        y[i, j] = model.addVar(vtype="B", name=f"use_{i}_{j}")
        
    for i, j in edges:
        model.addCons(x[i, j] <= capacity[i, j] * y[i, j], name=f"capacity_{i}_{j}")
        
    for n in nodes:
        inflow = quicksum(x[i, j] for i, j in edges if j == n)
        outflow = quicksum(x[i, j] for i, j in edges if i == n)
        model.addCons(outflow - inflow == supply.get(n, 0), name=f"flow_conservation_{n}")
        
    model.setObjective(quicksum(fixed_cost[i, j] * y[i, j] + variable_cost[i, j] * x[i, j] for i, j in edges), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
