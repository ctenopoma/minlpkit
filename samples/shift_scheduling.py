"""
Shift Scheduling Problem.

This model schedules employees to shifts to meet varying demand across periods,
minimizing total workforce size while ensuring minimum staffing levels and
shift constraints.
Reference: Dantzig, G. B. (1954). A comment on Edie's "Traffic delays at toll booths". 
Operations Research, 2(3), 339-341.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Shift_Scheduling")
    
    # Dummy data
    n_periods = 24
    periods = list(range(n_periods))
    
    demand = [10, 8, 5, 5, 8, 12, 15, 20, 25, 22, 18, 15, 18, 20, 22, 25, 28, 30, 25, 20, 15, 12, 10, 8]
    if infeasible:
        demand[0] = 500
        
    # Allowed shift patterns (start, length)
    shift_patterns = []
    for start in range(n_periods):
        shift_patterns.append((start, 8)) # 8-hour shift
        
    shifts = list(range(len(shift_patterns)))
    
    # Variables
    x = {s: model.addVar(vtype="I", lb=0, name=f"x_{s}") for s in shifts}
    
    # Objective
    model.setObjective(quicksum(x[s] for s in shifts), "minimize")
    
    # Constraints
    # Cover demand for each period
    for p in periods:
        # A shift covers this period if the period falls within [start, start + length - 1] modulo n_periods
        covering_shifts = []
        for s in shifts:
            start, length = shift_patterns[s]
            if (p - start) % n_periods < length:
                covering_shifts.append(s)
                
        model.addCons(quicksum(x[s] for s in covering_shifts) >= demand[p], name=f"demand_period_{p}")
        
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())
    else:
        print("No optimal solution found.")

if __name__ == "__main__":
    main()
