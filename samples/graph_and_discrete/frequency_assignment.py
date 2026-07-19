"""
Frequency Assignment Problem.
Assigns frequencies to communication links such that interference is minimized or avoided.
Reference: Aardal, K. I., et al. (2007). Models and solution techniques for frequency assignment problems. Annals of Operations Research.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("FrequencyAssignment")
    
    links = [1, 2, 3, 4]
    frequencies = [1, 2, 3]
    
    interference_edges = [(1, 2), (2, 3), (3, 4), (1, 4), (1, 3)]
    
    if infeasible:
        frequencies = [1, 2]
        
    x = {}
    for i in links:
        for f in frequencies:
            x[i, f] = model.addVar(vtype="B", name=f"assign_{i}_{f}")
            
    # Each link needs exactly one frequency
    for i in links:
        model.addCons(quicksum(x[i, f] for f in frequencies) == 1, name=f"one_freq_{i}")
        
    # Interference constraints
    for u, v in interference_edges:
        for f in frequencies:
            model.addCons(x[u, f] + x[v, f] <= 1, name=f"interference_{u}_{v}_{f}")
            
    # Minimize max frequency used
    max_f = model.addVar(vtype="C", name="max_freq")
    for i in links:
        for f in frequencies:
            model.addCons(max_f >= f * x[i, f], name=f"max_f_def_{i}_{f}")
            
    model.setObjective(max_f, "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
