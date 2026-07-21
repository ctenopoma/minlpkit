"""容量制約付き配送計画問題 (Capacitated Vehicle Routing Problem, CVRP) - MTZ定式化

事業ストーリー
--------------
物流センターの配送計画担当者が、倉庫(デポ)から出発する複数台のトラックで、
複数の顧客先に商品を届けるルートを決める。各トラックには積載容量の上限があり、
1台で全顧客を回りきれない場合は複数台に配送先を分担させる必要がある。使える
トラック台数にも上限があるため、「どの顧客をどのトラックが回るか」と「各トラック
内での訪問順」を同時に決め、総移動距離(燃料費・配送時間に直結)を最小化する。

各制約の業務的意味:
- **各顧客の一意訪問**: 各顧客にはちょうど1回、いずれかのトラックが訪問し出発する
  (未配達や重複配送を防ぐ)。
- **デポから出発する台数の上限**: デポから出るルートの本数は、保有するトラック
  台数を超えられない。
- **MTZ型の部分巡回路除去・容量制約**: 各顧客に「その地点までの積載量」を表す
  補助変数を持たせ、ルート上で積載量が需要分だけ単調に積み上がるよう縛ることで、
  デポを経由しない小さな閉ループの発生を防ぐと同時に、各トラックの積載量が容量を
  超えないことも保証する。

(元の参考文献: Miller, C. E., Tucker, A. W., & Zemlin, R. A. (1960).
Integer programming formulation of traveling salesman problems.
Journal of the ACM (JACM), 7(4), 326-329.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("CVRP_MTZ")
    
    # Dummy data
    n_customers = 5
    n_vehicles = 2
    capacity = 15
    
    nodes = list(range(n_customers + 1)) # 0 is depot
    customers = list(range(1, n_customers + 1))
    
    demand = {0: 0, 1: 4, 2: 5, 3: 3, 4: 7, 5: 2}
    if infeasible:
        demand[1] = 100 # Make it infeasible
        
    distance = {(i, j): ((i-j)**2 + (i*j)) % 10 + 1 for i in nodes for j in nodes if i != j}
    
    # Variables
    x = {}
    for i in nodes:
        for j in nodes:
            if i != j:
                x[i, j] = model.addVar(vtype="B", name=f"x_{i}_{j}")
                
    u = {}
    for i in customers:
        u[i] = model.addVar(vtype="C", lb=demand[i], ub=capacity, name=f"u_{i}")
        
    # Objective
    model.setObjective(quicksum(distance[i, j] * x[i, j] for i in nodes for j in nodes if i != j), "minimize")
    
    # Constraints
    # 1. Each customer is visited exactly once
    for i in customers:
        model.addCons(quicksum(x[i, j] for j in nodes if i != j) == 1, name=f"leave_{i}")
        model.addCons(quicksum(x[j, i] for j in nodes if i != j) == 1, name=f"enter_{i}")
        
    # 2. Number of vehicles leaving the depot
    model.addCons(quicksum(x[0, j] for j in customers) <= n_vehicles, name="max_vehicles")
    
    # 3. MTZ Subtour elimination and capacity
    for i in customers:
        for j in customers:
            if i != j:
                model.addCons(u[i] - u[j] + capacity * x[i, j] <= capacity - demand[j], name=f"mtz_{i}_{j}")
                
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
