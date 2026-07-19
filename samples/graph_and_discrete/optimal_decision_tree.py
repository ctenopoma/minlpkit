"""
Optimal Decision Tree (Simplified MIP).
Constructs a decision tree of fixed depth to minimize classification error.
Reference: Bertsimas, D., & Dunn, J. (2017). Optimal classification trees. Machine Learning.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("OptimalDecisionTree")
    
    # Depth 1 tree: 1 root split node (0), 2 leaf nodes (1, 2)
    split_nodes = [0]
    leaf_nodes = [1, 2]
    
    features = [0, 1]
    
    # (feature0, feature1, class)
    data = [
        (0.1, 0.2, 0),
        (0.8, 0.9, 1),
        (0.2, 0.1, 0),
        (0.9, 0.8, 1)
    ]
    classes = [0, 1]
    
    if infeasible:
        model.addCons(quicksum(model.addVar(name="dummy_inf") for _ in range(1)) <= -1, name="inf_cons")
        
    # Variables
    a = {} # a[t, f] = 1 if feature f is selected at node t
    b = {} # threshold at node t
    c = {} # c[t, k] = 1 if leaf t predicts class k
    z = {} # z[i, t] = 1 if sample i falls into leaf t
    
    for t in split_nodes:
        b[t] = model.addVar(vtype="C", name=f"b_{t}", lb=0, ub=1)
        for f in features:
            a[t, f] = model.addVar(vtype="B", name=f"a_{t}_{f}")
            
    for t in leaf_nodes:
        for k in classes:
            c[t, k] = model.addVar(vtype="B", name=f"c_{t}_{k}")
            
    for i in range(len(data)):
        for t in leaf_nodes:
            z[i, t] = model.addVar(vtype="B", name=f"z_{i}_{t}")
            
    # Splits must use one feature
    for t in split_nodes:
        model.addCons(quicksum(a[t, f] for f in features) == 1, name=f"split_feat_{t}")
        
    # Leaf must assign one class
    for t in leaf_nodes:
        model.addCons(quicksum(c[t, k] for k in classes) == 1, name=f"leaf_class_{t}")
        
    # Sample must fall into exactly one leaf
    for i in range(len(data)):
        model.addCons(quicksum(z[i, t] for t in leaf_nodes) == 1, name=f"sample_leaf_{i}")
        
    M = 2.0
    eps = 0.001
    for i, (x0, x1, y) in enumerate(data):
        expr = a[0, 0] * x0 + a[0, 1] * x1
        model.addCons(expr + eps <= b[0] + M * (1 - z[i, 1]), name=f"route_left_{i}")
        model.addCons(expr >= b[0] - M * (1 - z[i, 2]), name=f"route_right_{i}")
        
    # Error minimization
    L = {}
    for i in range(len(data)):
        L[i] = model.addVar(vtype="C", name=f"L_{i}", lb=0)
        
    for i, (x0, x1, y) in enumerate(data):
        for t in leaf_nodes:
            for k in classes:
                if k != y:
                    model.addCons(L[i] >= z[i, t] + c[t, k] - 1, name=f"err_{i}_{t}_{k}")
                    
    model.setObjective(quicksum(L[i] for i in range(len(data))), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
