"""
Portfolio Optimization with Cardinality Constraints (MIP).
Maximizes return (or minimizes risk) subject to a limit on the number of assets held.
Reference: Bienstock, D. (1996). Computational study of a family of mixed-integer quadratic programming problems. Mathematical programming.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("PortfolioMIP")
    
    assets = [1, 2, 3, 4, 5]
    returns = {1: 0.05, 2: 0.10, 3: 0.12, 4: 0.07, 5: 0.15}
    min_invest = 0.1
    max_invest = 0.5
    cardinality = 3
    
    if infeasible:
        min_invest = 0.4
        
    x = {} # investment weight
    z = {} # binary indicator for inclusion
    
    for i in assets:
        x[i] = model.addVar(vtype="C", name=f"weight_{i}", lb=0, ub=1)
        z[i] = model.addVar(vtype="B", name=f"include_{i}")
        
    model.addCons(quicksum(x[i] for i in assets) == 1.0, name="total_weight")
    
    for i in assets:
        model.addCons(x[i] >= min_invest * z[i], name=f"min_inv_{i}")
        model.addCons(x[i] <= max_invest * z[i], name=f"max_inv_{i}")
        
    model.addCons(quicksum(z[i] for i in assets) <= cardinality, name="cardinality_limit")
    
    model.setObjective(quicksum(returns[i] * x[i] for i in assets), "maximize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
