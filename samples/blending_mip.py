"""
Blending Problem (MIP variant)

This model determines the optimal blend of raw materials to produce a final product.
It includes discrete choices for selecting raw materials (minimum purchase quantities).
Relevant concept: Dantzig (1955) - The Diet Problem, extended with integer constraints.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    model = Model("BlendingMIP")
    
    # Dummy data
    materials = ["Mat1", "Mat2", "Mat3"]
    costs = {"Mat1": 15, "Mat2": 25, "Mat3": 20}
    protein = {"Mat1": 0.05, "Mat2": 0.15, "Mat3": 0.10}
    fat = {"Mat1": 0.10, "Mat2": 0.05, "Mat3": 0.08}
    
    req_product = 100
    min_protein = 0.08 * req_product
    max_fat = 0.08 * req_product
    min_purchase = 20
    
    # Variables
    x = {} # Amount of material
    y = {} # 1 if material is used
    for m in materials:
        x[m] = model.addVar(vtype="C", lb=0, name=f"amt_{m}")
        y[m] = model.addVar(vtype="B", name=f"use_{m}")
        
    # Constraints
    # Total product
    model.addCons(sum(x[m] for m in materials) == req_product, name="total_product")
    
    # Nutrition
    model.addCons(sum(protein[m] * x[m] for m in materials) >= min_protein, name="min_protein")
    model.addCons(sum(fat[m] * x[m] for m in materials) <= max_fat, name="max_fat")
    
    # Logical constraints and min purchase
    bigM = 1000
    for m in materials:
        model.addCons(x[m] <= bigM * y[m], name=f"logic_upper_{m}")
        model.addCons(x[m] >= min_purchase * y[m], name=f"logic_lower_{m}")
        
    if infeasible:
        model.addCons(sum(x[m] for m in materials) == req_product + 10, name="inf_constraint")
        
    # Objective
    model.setObjective(sum(costs[m] * x[m] for m in materials), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
