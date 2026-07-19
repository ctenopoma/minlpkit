"""
Hub Location Problem.

This model determines the optimal location of hubs and the assignment of
spoke nodes to hubs to minimize total transportation costs.
Reference: O'Kelly, M. E. (1987). A quadratic integer program for the location
of interacting hub facilities. European journal of operational research, 32(3), 393-404.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Hub_Location")
    
    n_nodes = 5
    nodes = list(range(n_nodes))
    
    p = 2 # Number of hubs to locate
    
    # Dummy flow and distance data
    flow = {(i, j): (i + j + 1) * 10 for i in nodes for j in nodes}
    distance = {(i, j): abs(i - j) * 5 + 2 for i in nodes for j in nodes}
    
    alpha = 0.5 # Discount factor between hubs
    
    # Variables
    # x[i, k] = 1 if node i is allocated to hub k
    x = {}
    for i in nodes:
        for k in nodes:
            x[i, k] = model.addVar(vtype="B", name=f"x_{i}_{k}")
            
    # y[i, k, m, j] = fraction of flow from i to j routed via hubs k and m
    y = {}
    for i in nodes:
        for k in nodes:
            for m in nodes:
                for j in nodes:
                    y[i, k, m, j] = model.addVar(vtype="C", lb=0, name=f"y_{i}_{k}_{m}_{j}")
                    
    # Objective
    obj = quicksum(distance[i, k] * y[i, k, m, j] * flow[i, j] + 
                   alpha * distance[k, m] * y[i, k, m, j] * flow[i, j] +
                   distance[m, j] * y[i, k, m, j] * flow[i, j]
                   for i in nodes for k in nodes for m in nodes for j in nodes)
    model.setObjective(obj, "minimize")
    
    # Constraints
    # Exactly p hubs
    model.addCons(quicksum(x[k, k] for k in nodes) == p, name="p_hubs")
    
    if infeasible:
        model.addCons(quicksum(x[k, k] for k in nodes) == p + 10, name="inf_hubs")
        
    # Each node assigned to exactly one hub
    for i in nodes:
        model.addCons(quicksum(x[i, k] for k in nodes) == 1, name=f"assign_{i}")
        
    # Can only assign to open hubs
    for i in nodes:
        for k in nodes:
            model.addCons(x[i, k] <= x[k, k], name=f"open_hub_{i}_{k}")
            
    # Routing constraints
    for i in nodes:
        for j in nodes:
            model.addCons(quicksum(y[i, k, m, j] for k in nodes for m in nodes) == 1, name=f"flow_{i}_{j}")
            
    for i in nodes:
        for j in nodes:
            for k in nodes:
                model.addCons(quicksum(y[i, k, m, j] for m in nodes) == x[i, k], name=f"route_start_{i}_{j}_{k}")
                
    for i in nodes:
        for j in nodes:
            for m in nodes:
                model.addCons(quicksum(y[i, k, m, j] for k in nodes) == x[j, m], name=f"route_end_{i}_{j}_{m}")
                
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
