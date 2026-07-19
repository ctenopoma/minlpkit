"""
Feature Selection for Regression (MIP).
Selects a subset of features to minimize regression error with a constraint on the number of features.
Reference: Bertsimas, D., King, A., & Mazumder, R. (2016). Best subset selection via a modern optimization lens. The annals of statistics.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("FeatureSelection")
    
    # 3 samples, 4 features
    X = [
        [1.0, 0.5, 0.2, 0.1],
        [0.5, 1.0, 0.3, 0.2],
        [0.2, 0.3, 1.0, 0.5]
    ]
    y = [1.5, 1.8, 1.2]
    
    n_samples = len(X)
    n_features = len(X[0])
    k_max = 2 # max features
    
    if infeasible:
        k_max = -1
        
    M = 10.0
    
    beta = {}
    z = {}
    error = {}
    
    for j in range(n_features):
        beta[j] = model.addVar(vtype="C", name=f"beta_{j}", lb=-M, ub=M)
        z[j] = model.addVar(vtype="B", name=f"z_{j}")
        
    for i in range(n_samples):
        # absolute error formulation for simplicity
        error[i] = model.addVar(vtype="C", name=f"error_{i}", lb=0)
        
    # Big-M constraints
    for j in range(n_features):
        model.addCons(beta[j] <= M * z[j], name=f"bigM_up_{j}")
        model.addCons(beta[j] >= -M * z[j], name=f"bigM_low_{j}")
        
    model.addCons(quicksum(z[j] for j in range(n_features)) <= k_max, name="sparsity")
    
    # Error constraints
    for i in range(n_samples):
        pred = quicksum(X[i][j] * beta[j] for j in range(n_features))
        model.addCons(error[i] >= y[i] - pred, name=f"err_up_{i}")
        model.addCons(error[i] >= pred - y[i], name=f"err_low_{i}")
        
    model.setObjective(quicksum(error[i] for i in range(n_samples)), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
