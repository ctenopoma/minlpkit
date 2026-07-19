"""
Set Cover Problem
This model selects a minimum number of sets such that all elements in the universe are covered.
Reference: Karp, R. M. (1972). Reducibility among combinatorial problems. 
In Complexity of computer computations (pp. 85-103). Springer, Boston, MA.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Set_Cover")
    
    # Dummy data
    universe = [1, 2, 3, 4, 5]
    sets = {
        "S1": [1, 2, 3],
        "S2": [2, 4],
        "S3": [3, 4],
        "S4": [4, 5]
    }
    
    if infeasible:
        sets = {"S1": [1]} # Cannot cover 2,3,4,5
        
    # Variables
    x = {}
    for s_name in sets.keys():
        x[s_name] = m.addVar(vtype="B", name=f"x_{s_name}")
        
    # Objective
    m.setObjective(sum(x[s] for s in sets.keys()), "minimize")
    
    # Constraints
    for e in universe:
        covering_sets = [s for s, elements in sets.items() if e in elements]
        m.addCons(sum(x[s] for s in covering_sets) >= 1, name=f"Cover_{e}")
        
    return m

def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value:", m.getObjVal())
    else:
        print("Status:", m.getStatus())

if __name__ == "__main__":
    main()
