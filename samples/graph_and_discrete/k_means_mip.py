"""
K-Means Clustering (MIP Formulation)
This model represents the k-means clustering problem as a Mixed-Integer Programming (MIP) problem.
Reference: Aloise, D., Deshpande, A., Hansen, P., & Popat, P. (2009). 
NP-hardness of Euclidean sum-of-squares clustering. Machine learning, 75(2), 245-248.
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("K-Means_MIP")
    
    # Dummy data
    points = [(0, 0), (1, 1), (10, 10), (11, 11), (5, 5)]
    N = len(points)
    K = 2 # Number of clusters
    
    if infeasible:
        K = 0 # Invalid
    
    # Variables
    # x[i, j] = 1 if point i is assigned to cluster center j (which is point j)
    x = {}
    for i in range(N):
        for j in range(N):
            x[i, j] = m.addVar(vtype="B", name=f"x_{i}_{j}")
            
    # y[j] = 1 if point j is chosen as a cluster center
    y = {}
    for j in range(N):
        y[j] = m.addVar(vtype="B", name=f"y_{j}")
        
    # Objective: minimize sum of squared distances
    obj = 0
    for i in range(N):
        for j in range(N):
            dist_sq = (points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2
            obj += dist_sq * x[i, j]
    m.setObjective(obj, "minimize")
    
    # Constraints
    # 1. Exactly K centers must be chosen
    m.addCons(sum(y[j] for j in range(N)) == K, name="Num_Clusters")
    
    # 2. Each point is assigned to exactly one center
    for i in range(N):
        m.addCons(sum(x[i, j] for j in range(N)) == 1, name=f"Assign_{i}")
        
    # 3. A point can only be assigned to j if j is a center
    for i in range(N):
        for j in range(N):
            m.addCons(x[i, j] <= y[j], name=f"Valid_Center_{i}_{j}")
            
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
