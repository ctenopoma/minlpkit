"""
Steiner Tree Problem in Graphs.
Finds a minimum-weight tree connecting a designated set of terminal nodes.
Reference: Hwang, F. K., Richards, D. S., & Winter, P. (1992). The Steiner tree problem. Elsevier.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("SteinerTree")
    
    nodes = [1, 2, 3, 4, 5, 6]
    terminals = [1, 3, 6]
    root = terminals[0]
    
    edges = [(1, 2), (2, 3), (1, 4), (4, 5), (5, 6), (2, 5), (3, 6)]
    costs = {(1, 2): 2, (2, 3): 2, (1, 4): 10, (4, 5): 10, (5, 6): 10, (2, 5): 1, (3, 6): 2}
    
    if infeasible:
        edges = [(1, 2), (2, 3), (1, 4), (4, 5)] # 6 is disconnected
        costs = {(1, 2): 2, (2, 3): 2, (1, 4): 10, (4, 5): 10}
        
    # Bidirectional edges for flow
    arcs = []
    for u, v in edges:
        arcs.append((u, v))
        arcs.append((v, u))
        
    y = {}
    for u, v in edges:
        y[u, v] = model.addVar(vtype="B", name=f"edge_{u}_{v}")
        
    x = {}
    for t in terminals:
        if t != root:
            for u, v in arcs:
                x[t, u, v] = model.addVar(vtype="C", name=f"flow_{t}_{u}_{v}", lb=0)
                
    for t in terminals:
        if t != root:
            for n in nodes:
                inflow = quicksum(x[t, i, j] for i, j in arcs if j == n)
                outflow = quicksum(x[t, i, j] for i, j in arcs if i == n)
                
                if n == root:
                    demand = 1
                elif n == t:
                    demand = -1
                else:
                    demand = 0
                    
                model.addCons(outflow - inflow == demand, name=f"flow_cons_{t}_{n}")
                
            for u, v in arcs:
                # Flow can only go if edge is selected
                edge_var = y[u, v] if (u, v) in edges else y[v, u]
                model.addCons(x[t, u, v] <= edge_var, name=f"cap_{t}_{u}_{v}")
                
    model.setObjective(quicksum(costs[u, v] * y[u, v] for u, v in edges), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
