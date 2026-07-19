"""
Microgrid Energy Management System (EMS)
This model optimizes the scheduling of a microgrid containing a diesel generator, solar power, and a battery.
Reference: Parisio, A., Rikos, E., & Glielmo, L. (2014). 
A model predictive control approach to microgrid operation optimization. 
IEEE Transactions on Control Systems Technology, 22(5), 1813-1827.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Microgrid_EMS")
    
    # Dummy data for 4 hours
    T = 4
    demand = [50, 60, 40, 70]
    solar_gen = [10, 20, 30, 0]
    diesel_cost = 5.0
    diesel_max = 50
    battery_max_cap = 100
    battery_max_charge = 20
    
    if infeasible:
        diesel_max = 0
        battery_max_charge = 0
    
    # Variables
    diesel = {}
    charge = {}
    discharge = {}
    soc = {} # State of charge
    
    for t in range(T):
        diesel[t] = m.addVar(vtype="C", lb=0, ub=diesel_max, name=f"diesel_{t}")
        charge[t] = m.addVar(vtype="C", lb=0, ub=battery_max_charge, name=f"charge_{t}")
        discharge[t] = m.addVar(vtype="C", lb=0, ub=battery_max_charge, name=f"discharge_{t}")
        soc[t] = m.addVar(vtype="C", lb=0, ub=battery_max_cap, name=f"soc_{t}")
        
    # Objective
    m.setObjective(sum(diesel_cost * diesel[t] for t in range(T)), "minimize")
    
    # Constraints
    for t in range(T):
        # Power balance
        m.addCons(diesel[t] + solar_gen[t] + discharge[t] - charge[t] == demand[t], name=f"Power_Balance_{t}")
        
        # SOC dynamics
        if t == 0:
            m.addCons(soc[t] == 50 + charge[t] - discharge[t], name=f"SOC_Dyn_{t}")
        else:
            m.addCons(soc[t] == soc[t-1] + charge[t] - discharge[t], name=f"SOC_Dyn_{t}")
            
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
