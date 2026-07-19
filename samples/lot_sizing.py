"""
Multi-period Lot Sizing Problem

This model minimizes the total cost of production, setup, and inventory holding
to meet the demand over a planning horizon.
Relevant concept: Wagner-Whitin algorithm (1958) - Dynamic version of the economic lot size model.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    model = Model("LotSizing")
    
    # Dummy data
    periods = 5
    demand = [20, 50, 10, 40, 30]
    setup_cost = 100
    prod_cost = 5
    hold_cost = 2
    capacity = 60
    
    # Variables
    x = {} # Production amount
    y = {} # Setup indicator
    s = {} # Inventory level
    
    for t in range(periods):
        x[t] = model.addVar(vtype="C", lb=0, name=f"prod_{t}")
        y[t] = model.addVar(vtype="B", name=f"setup_{t}")
        s[t] = model.addVar(vtype="C", lb=0, name=f"inv_{t}")
        
    # Constraints
    for t in range(periods):
        # Inventory balance
        if t == 0:
            model.addCons(x[t] - s[t] == demand[t], name=f"inv_bal_{t}")
        else:
            model.addCons(s[t-1] + x[t] - s[t] == demand[t], name=f"inv_bal_{t}")
            
        # Capacity and setup constraint
        model.addCons(x[t] <= capacity * y[t], name=f"cap_setup_{t}")
        
    if infeasible:
        model.addCons(x[0] <= 0, name="inf_constraint")
        
    # Objective
    model.setObjective(sum(setup_cost * y[t] + prod_cost * x[t] + hold_cost * s[t] for t in range(periods)), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
