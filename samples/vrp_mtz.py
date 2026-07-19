"""
Capacitated Vehicle Routing Problem (CVRP) using MTZ formulation.

This model implements the classic Miller-Tucker-Zemlin (MTZ) formulation
for subtour elimination in the CVRP.
Reference: Miller, C. E., Tucker, A. W., & Zemlin, R. A. (1960). 
Integer programming formulation of traveling salesman problems. 
Journal of the ACM (JACM), 7(4), 326-329.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("CVRP_MTZ")
    
    # Dummy data
    n_customers = 5
    n_vehicles = 2
    capacity = 15
    
    nodes = list(range(n_customers + 1)) # 0 is depot
    customers = list(range(1, n_customers + 1))
    
    demand = {0: 0, 1: 4, 2: 5, 3: 3, 4: 7, 5: 2}
    if infeasible:
        demand[1] = 100 # Make it infeasible
        
    distance = {(i, j): ((i-j)**2 + (i*j)) % 10 + 1 for i in nodes for j in nodes if i != j}
    
    # Variables
    x = {}
    for i in nodes:
        for j in nodes:
            if i != j:
                x[i, j] = model.addVar(vtype="B", name=f"x_{i}_{j}")
                
    u = {}
    for i in customers:
        u[i] = model.addVar(vtype="C", lb=demand[i], ub=capacity, name=f"u_{i}")
        
    # Objective
    model.setObjective(quicksum(distance[i, j] * x[i, j] for i in nodes for j in nodes if i != j), "minimize")
    
    # Constraints
    # 1. Each customer is visited exactly once
    for i in customers:
        model.addCons(quicksum(x[i, j] for j in nodes if i != j) == 1, name=f"leave_{i}")
        model.addCons(quicksum(x[j, i] for j in nodes if i != j) == 1, name=f"enter_{i}")
        
    # 2. Number of vehicles leaving the depot
    model.addCons(quicksum(x[0, j] for j in customers) <= n_vehicles, name="max_vehicles")
    
    # 3. MTZ Subtour elimination and capacity
    for i in customers:
        for j in customers:
            if i != j:
                model.addCons(u[i] - u[j] + capacity * x[i, j] <= capacity - demand[j], name=f"mtz_{i}_{j}")
                
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
