"""
Maximum Clique Problem (MIP Formulation)
This model finds the largest complete subgraph (clique) in a given graph.
Reference: Bomze, I. M., Budinich, M., Pardalos, P. M., & Pelillo, M. (1999). 
The maximum clique problem. Handbook of combinatorial optimization, 1-74.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Max_Clique")
    
    # Dummy data: Graph with 5 vertices
    # Edge list (0-indexed)
    edges = [(0, 1), (0, 2), (1, 2), (1, 3), (2, 3), (3, 4)]
    V = 5
    
    if infeasible:
        m.addCons(0 == 1, name="Infeasible_Cons") # Force infeasibility
        
    # Build adjacency matrix
    adj = {i: set() for i in range(V)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
        
    # Variables
    x = {}
    for i in range(V):
        x[i] = m.addVar(vtype="B", name=f"x_{i}")
        
    # Objective: Maximize clique size (minimize -size)
    m.setObjective(sum(-x[i] for i in range(V)), "minimize")
    
    # Constraints: If i and j are not connected, they cannot both be in the clique
    for i in range(V):
        for j in range(i + 1, V):
            if j not in adj[i]:
                m.addCons(x[i] + x[j] <= 1, name=f"No_Edge_{i}_{j}")
                
    return m

def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value (Max Clique Size):", -m.getObjVal())
    else:
        print("Status:", m.getStatus())

if __name__ == "__main__":
    main()
