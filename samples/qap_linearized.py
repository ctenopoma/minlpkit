"""
Linearized Quadratic Assignment Problem (QAP)

Assigns facilities to locations to minimize flow * distance costs.
Linearized using Adams-Johnson formulation.
Relevant concept: Koopmans and Beckmann (1957) - Assignment problems and the location of economic activities.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("QAPLinearized")
    
    # Dummy data
    n = 3
    flow = [
        [0, 5, 2],
        [5, 0, 3],
        [2, 3, 0]
    ]
    dist = [
        [0, 10, 20],
        [10, 0, 15],
        [20, 15, 0]
    ]
    
    # Variables
    x = {} # x[i, k] = 1 if facility i is assigned to location k
    y = {} # y[i, k, j, l] = x[i, k] * x[j, l]
    
    for i in range(n):
        for k in range(n):
            x[i, k] = model.addVar(vtype="B", name=f"x_{i}_{k}")
            for j in range(n):
                for l in range(n):
                    if i != j and k != l:
                        y[i, k, j, l] = model.addVar(vtype="C", lb=0, name=f"y_{i}_{k}_{j}_{l}")
                        
    # Constraints
    # Assignment
    for i in range(n):
        model.addCons(quicksum(x[i, k] for k in range(n)) == 1, name=f"assign_fac_{i}")
    for k in range(n):
        model.addCons(quicksum(x[i, k] for i in range(n)) == 1, name=f"assign_loc_{k}")
        
    # Linearization
    for i in range(n):
        for k in range(n):
            for j in range(n):
                if i != j:
                    model.addCons(quicksum(y[i, k, j, l] for l in range(n) if l != k) == x[i, k], name=f"lin_{i}_{k}_{j}")
                    
    # Symmetry
    for i in range(n):
        for k in range(n):
            for j in range(n):
                for l in range(n):
                    if i != j and k != l and i < j:
                        model.addCons(y[i, k, j, l] == y[j, l, i, k], name=f"sym_{i}_{k}_{j}_{l}")
                        
    if infeasible:
        model.addCons(x[0, 0] + x[0, 1] + x[0, 2] == 0, name="inf_constraint")
        
    # Objective
    model.setObjective(quicksum(flow[i][j] * dist[k][l] * y[i, k, j, l] 
                                for i in range(n) for k in range(n) 
                                for j in range(n) for l in range(n) if i != j and k != l), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
