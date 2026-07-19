"""
Sports Scheduling Problem

This model formulates a single round-robin tournament scheduling problem.
It aims to minimize the travel distance of teams playing away games.
Relevant concept: Nemhauser and Trick (1998) - Scheduling a major college basketball conference.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("SportsScheduling")
    
    # Dummy data
    teams = [1, 2, 3, 4]
    weeks = [1, 2, 3]
    # distance matrix
    dist = {
        (1,2): 10, (1,3): 20, (1,4): 30,
        (2,1): 10, (2,3): 15, (2,4): 25,
        (3,1): 20, (3,2): 15, (3,4): 10,
        (4,1): 30, (4,2): 25, (4,3): 10
    }
    
    # Variables
    x = {} # x[i, j, w] = 1 if team i plays at team j in week w
    for i in teams:
        for j in teams:
            if i != j:
                for w in weeks:
                    x[i, j, w] = model.addVar(vtype="B", name=f"x_{i}_{j}_{w}")
                    
    # Constraints
    # Each team plays exactly one game per week
    for i in teams:
        for w in weeks:
            model.addCons(
                quicksum(x[i, j, w] for j in teams if i != j) + 
                quicksum(x[j, i, w] for j in teams if i != j) == 1,
                name=f"one_game_{i}_{w}"
            )
            
    # Each team plays every other team exactly once
    for i in teams:
        for j in teams:
            if i != j:
                model.addCons(
                    quicksum(x[i, j, w] for w in weeks) + 
                    quicksum(x[j, i, w] for w in weeks) == 1,
                    name=f"play_once_{i}_{j}"
                )
    
    if infeasible:
        model.addCons(quicksum(x[i, j, w] for i in teams for j in teams if i != j for w in weeks) == 0, name="inf_constraint")
        
    # Objective: Minimize travel distance for away teams
    model.setObjective(quicksum(dist[i, j] * x[i, j, w] for i in teams for j in teams if i != j for w in weeks), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
