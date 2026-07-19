"""
Cash Flow Matching Problem.
Dedicates a portfolio of bonds to meet a schedule of liabilities.
Reference: Fabozzi, F. J. (2000). Fixed income analysis. John Wiley & Sons.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("CashFlowMatching")
    
    periods = [1, 2, 3, 4, 5]
    liabilities = {1: 100, 2: 120, 3: 150, 4: 200, 5: 250}
    
    bonds = ["A", "B", "C"]
    bond_prices = {"A": 95, "B": 102, "C": 105}
    
    # coupon + principal payments
    cash_flows = {
        "A": {1: 5, 2: 5, 3: 105, 4: 0, 5: 0},
        "B": {1: 0, 2: 0, 3: 0, 4: 10, 5: 110},
        "C": {1: 6, 2: 6, 3: 6, 4: 6, 5: 106}
    }
    
    reinvestment_rate = 0.02
    
    if infeasible:
        bonds = ["A"]
        
    x = {} # number of bonds to purchase
    s = {} # surplus cash at period t
    
    for b in bonds:
        x[b] = model.addVar(vtype="I", name=f"bond_{b}", lb=0)
        
    for t in periods:
        s[t] = model.addVar(vtype="C", name=f"surplus_{t}", lb=0)
        
    for t in periods:
        cf_in = quicksum(cash_flows[b].get(t, 0) * x[b] for b in bonds)
        if t == 1:
            model.addCons(cf_in - s[t] == liabilities[t], name=f"balance_{t}")
        else:
            model.addCons(cf_in + (1 + reinvestment_rate) * s[t-1] - s[t] == liabilities[t], name=f"balance_{t}")
            
    model.setObjective(quicksum(bond_prices[b] * x[b] for b in bonds), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
