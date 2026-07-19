"""
Pumped-Storage Hydroelectric Scheduling
This model schedules pumping and generating for a pumped-storage hydroelectric plant to maximize profit.
Reference: Garcia-Gonzalez, J., de la Muela, R. M. R., Santos, L. M., & Gonzalez, A. M. (2007). 
Stochastic joint optimization of wind generation and pumped-storage units in an electricity market. 
IEEE Transactions on power systems, 23(2), 460-468.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Hydro_Scheduling")
    
    # Dummy data for 4 hours
    T = 4
    prices = [20, 15, 60, 80] # High prices later
    p_max = 50
    g_max = 50
    v_max = 200
    eff = 0.9
    
    if infeasible:
        v_max = -10
        
    # Variables
    pump = {}
    gen = {}
    vol = {}
    is_pump = {}
    
    for t in range(T):
        pump[t] = m.addVar(vtype="C", lb=0, ub=p_max, name=f"pump_{t}")
        gen[t] = m.addVar(vtype="C", lb=0, ub=g_max, name=f"gen_{t}")
        vol[t] = m.addVar(vtype="C", lb=0, ub=v_max, name=f"vol_{t}")
        is_pump[t] = m.addVar(vtype="B", name=f"is_pump_{t}")
        
    # Objective (Maximize profit)
    # PySCIPOpt minimizes by default, so we minimize -profit
    profit = sum(prices[t] * (gen[t] - pump[t]) for t in range(T))
    m.setObjective(-profit, "minimize")
    
    # Constraints
    for t in range(T):
        # Mutual exclusion
        m.addCons(pump[t] <= p_max * is_pump[t], name=f"Pump_Exc_{t}")
        m.addCons(gen[t] <= g_max * (1 - is_pump[t]), name=f"Gen_Exc_{t}")
        
        # Volume dynamics
        if t == 0:
            m.addCons(vol[t] == 100 + eff * pump[t] - gen[t] / eff, name=f"Vol_Dyn_{t}")
        else:
            m.addCons(vol[t] == vol[t-1] + eff * pump[t] - gen[t] / eff, name=f"Vol_Dyn_{t}")
            
    return m

def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value:", -m.getObjVal())
    else:
        print("Status:", m.getStatus())

if __name__ == "__main__":
    main()
