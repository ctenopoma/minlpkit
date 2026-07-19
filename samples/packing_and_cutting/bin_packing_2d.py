"""
2D Bin Packing Problem

This model packs a set of rectangular items into the minimum number of identical rectangular bins.
It ensures that items do not overlap and do not exceed bin boundaries.
Relevant concept: Lodi et al. (2002) - Two-dimensional packing problems: A survey.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("BinPacking2D")
    
    # Dummy data
    bin_W = 10
    bin_H = 10
    items = [(3, 4), (5, 5), (6, 2), (4, 4), (5, 3)]
    n = len(items)
    max_bins = 3
    
    # Variables
    y = {} # y[k] = 1 if bin k is used
    x = {} # x[i, k] = 1 if item i is in bin k
    pos_x = {} # x-coordinate of bottom-left corner of item i
    pos_y = {} # y-coordinate of bottom-left corner of item i
    
    for k in range(max_bins):
        y[k] = model.addVar(vtype="B", name=f"use_bin_{k}")
        for i in range(n):
            x[i, k] = model.addVar(vtype="B", name=f"assign_{i}_{k}")
            
    for i in range(n):
        pos_x[i] = model.addVar(vtype="C", lb=0, name=f"pos_x_{i}")
        pos_y[i] = model.addVar(vtype="C", lb=0, name=f"pos_y_{i}")
        
    # Constraints
    # Each item to exactly one bin
    for i in range(n):
        model.addCons(quicksum(x[i, k] for k in range(max_bins)) == 1, name=f"assign_item_{i}")
        
    # Boundaries
    for i in range(n):
        w, h = items[i]
        model.addCons(pos_x[i] + w <= bin_W, name=f"bound_x_{i}")
        model.addCons(pos_y[i] + h <= bin_H, name=f"bound_y_{i}")
        
    # Bin usage limit
    for i in range(n):
        for k in range(max_bins):
            model.addCons(x[i, k] <= y[k], name=f"usage_{i}_{k}")
            
    # Non-overlapping constraints (simplified using big-M)
    bigM = max(bin_W, bin_H)
    z = {} # relative position indicators
    for i in range(n):
        for j in range(n):
            if i < j:
                # 4 boolean variables for relative positions
                z[i, j, 0] = model.addVar(vtype="B", name=f"z_{i}_{j}_left")
                z[i, j, 1] = model.addVar(vtype="B", name=f"z_{i}_{j}_right")
                z[i, j, 2] = model.addVar(vtype="B", name=f"z_{i}_{j}_below")
                z[i, j, 3] = model.addVar(vtype="B", name=f"z_{i}_{j}_above")
                
                # If they are in the same bin, they must not overlap
                same_bin = model.addVar(vtype="B", name=f"same_bin_{i}_{j}")
                for k in range(max_bins):
                    model.addCons(same_bin >= x[i, k] + x[j, k] - 1, name=f"same_bin_lower_{i}_{j}_{k}")
                
                w_i, h_i = items[i]
                w_j, h_j = items[j]
                
                model.addCons(pos_x[i] + w_i <= pos_x[j] + bigM * (1 - z[i, j, 0]), name=f"no_ovlap_l_{i}_{j}")
                model.addCons(pos_x[j] + w_j <= pos_x[i] + bigM * (1 - z[i, j, 1]), name=f"no_ovlap_r_{i}_{j}")
                model.addCons(pos_y[i] + h_i <= pos_y[j] + bigM * (1 - z[i, j, 2]), name=f"no_ovlap_b_{i}_{j}")
                model.addCons(pos_y[j] + h_j <= pos_y[i] + bigM * (1 - z[i, j, 3]), name=f"no_ovlap_a_{i}_{j}")
                
                model.addCons(z[i, j, 0] + z[i, j, 1] + z[i, j, 2] + z[i, j, 3] >= same_bin, name=f"no_ovlap_sum_{i}_{j}")
                
    if infeasible:
        model.addCons(quicksum(y[k] for k in range(max_bins)) == 0, name="inf_constraint")
        
    # Objective
    model.setObjective(quicksum(y[k] for k in range(max_bins)), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
