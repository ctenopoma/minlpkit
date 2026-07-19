"""
Multidimensional Knapsack Problem (MKP)

This model maximizes the total value of items selected subject to multiple resource constraints.
Relevant concept: Weingartner and Ness (1967) - Methods for the solution of the multidimensional 0/1 knapsack problem.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("MKP")
    
    # Dummy data
    items = 5
    resources = 3
    values = [50, 40, 30, 20, 60]
    weights = [
        [12, 5, 8, 3, 15],
        [8, 10, 5, 6, 9],
        [5, 4, 12, 7, 8]
    ]
    capacities = [25, 20, 20]
    
    # Variables
    x = {} # 1 if item i is selected
    for i in range(items):
        x[i] = model.addVar(vtype="B", name=f"x_{i}")
        
    # Constraints
    for r in range(resources):
        model.addCons(quicksum(weights[r][i] * x[i] for i in range(items)) <= capacities[r], name=f"capacity_{r}")
        
    if infeasible:
        model.addCons(quicksum(x[i] for i in range(items)) >= items + 1, name="inf_constraint")
        
    # Objective
    model.setObjective(quicksum(values[i] * x[i] for i in range(items)), "maximize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
