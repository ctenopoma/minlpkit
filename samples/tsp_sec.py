"""
Traveling Salesman Problem (TSP) with Subtour Elimination Constraints.

This model implements the TSP using MTZ-like continuous variables
for subtour elimination (a simplified version of MTZ for TSP).
Reference: Dantzig, G., Fulkerson, R., & Johnson, S. (1954).
Solution of a large-scale traveling-salesman problem.
Journal of the operations research society of America, 2(4), 393-410.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("TSP")
    
    n_nodes = 6
    nodes = list(range(n_nodes))
    
    # Dummy distance matrix
    distance = {(i, j): abs(i - j) * 2 + (i * j) % 3 for i in nodes for j in nodes if i != j}
    
    # Variables
    x = {}
    for i in nodes:
        for j in nodes:
            if i != j:
                x[i, j] = model.addVar(vtype="B", name=f"x_{i}_{j}")
                
    u = {}
    for i in range(1, n_nodes):
        u[i] = model.addVar(vtype="C", lb=1, ub=n_nodes-1, name=f"u_{i}")
        
    # Objective
    model.setObjective(quicksum(distance[i, j] * x[i, j] for i in nodes for j in nodes if i != j), "minimize")
    
    # Degree constraints
    for i in nodes:
        model.addCons(quicksum(x[i, j] for j in nodes if i != j) == 1, name=f"out_degree_{i}")
        model.addCons(quicksum(x[j, i] for j in nodes if i != j) == 1, name=f"in_degree_{i}")
        
    if infeasible:
        model.addCons(quicksum(x[i, j] for i in nodes for j in nodes if i != j) <= 2, name="inf_cons")
        
    # Subtour elimination
    for i in range(1, n_nodes):
        for j in range(1, n_nodes):
            if i != j:
                model.addCons(u[i] - u[j] + (n_nodes - 1) * x[i, j] <= n_nodes - 2, name=f"sec_{i}_{j}")
                
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
