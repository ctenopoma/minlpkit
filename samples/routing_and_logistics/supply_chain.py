"""
Multi-echelon Supply Chain Network Design.

This model determines which plants and distribution centers to open
and the flow of products between them to minimize total costs.
Reference: Geoffrion, A. M., & Graves, G. W. (1974). 
Multicommodity distribution system design by Benders decomposition. 
Management science, 20(5), 822-844.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Supply_Chain")
    
    plants = [1, 2]
    dcs = [1, 2, 3]
    customers = [1, 2, 3, 4]
    
    # Dummy data
    plant_cap = {1: 100, 2: 120}
    plant_fixed = {1: 500, 2: 600}
    dc_cap = {1: 80, 2: 90, 3: 70}
    dc_fixed = {1: 200, 2: 250, 3: 150}
    
    demand = {1: 40, 2: 30, 3: 50, 4: 20}
    if infeasible:
        demand[1] = 1000
        
    cost_p_dc = {(p, d): (p+d)*2 for p in plants for d in dcs}
    cost_dc_c = {(d, c): (d+c)*1.5 for d in dcs for c in customers}
    
    # Variables
    y_p = {p: model.addVar(vtype="B", name=f"y_p_{p}") for p in plants}
    y_d = {d: model.addVar(vtype="B", name=f"y_d_{d}") for d in dcs}
    
    x_p_d = {(p, d): model.addVar(vtype="C", lb=0, name=f"x_pd_{p}_{d}") for p in plants for d in dcs}
    x_d_c = {(d, c): model.addVar(vtype="C", lb=0, name=f"x_dc_{d}_{c}") for d in dcs for c in customers}
    
    # Objective
    obj = quicksum(plant_fixed[p] * y_p[p] for p in plants) + \
          quicksum(dc_fixed[d] * y_d[d] for d in dcs) + \
          quicksum(cost_p_dc[p, d] * x_p_d[p, d] for p in plants for d in dcs) + \
          quicksum(cost_dc_c[d, c] * x_d_c[d, c] for d in dcs for c in customers)
    model.setObjective(obj, "minimize")
    
    # Constraints
    # Meet demand
    for c in customers:
        model.addCons(quicksum(x_d_c[d, c] for d in dcs) == demand[c], name=f"demand_{c}")
        
    # DC flow balance
    for d in dcs:
        model.addCons(quicksum(x_p_d[p, d] for p in plants) == quicksum(x_d_c[d, c] for c in customers), name=f"flow_dc_{d}")
        
    # Plant capacity
    for p in plants:
        model.addCons(quicksum(x_p_d[p, d] for d in dcs) <= plant_cap[p] * y_p[p], name=f"cap_p_{p}")
        
    # DC capacity
    for d in dcs:
        model.addCons(quicksum(x_d_c[d, c] for c in customers) <= dc_cap[d] * y_d[d], name=f"cap_d_{d}")
        
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
