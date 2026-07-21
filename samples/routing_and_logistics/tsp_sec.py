"""巡回セールスマン問題(部分巡回路除去付き) (Traveling Salesman Problem with Subtour Elimination Constraints)

事業ストーリー
--------------
訪問営業担当者が、拠点(自社オフィス)から出発して全ての訪問先を1回ずつ回り、
再び拠点に戻ってくる最短ルートを決める。訪問先同士の移動距離はあらかじめ
分かっており、総移動距離を最小化する巡回順を求める必要がある。単純に「各地点は
1回入って1回出る」という制約だけでは、全体を1周する経路ではなく複数の小さな
閉ループ(部分巡回路)に分裂した解が最適に見えてしまうため、それを禁止する
補助変数を導入する。

各制約の業務的意味:
- **出次数・入次数制約**: 各訪問先には他のちょうど1地点から到着し、他のちょうど
  1地点へ出発する(全地点を1回ずつ訪問する経路の必要条件)。
- **部分巡回路除去制約(MTZ型)**: 各地点に訪問順を表す補助変数を持たせ、経路上で
  訪問順が単調に増加するよう縛ることで、全体を含まない小さな閉ループの発生を防ぐ。

(元の参考文献: Dantzig, G., Fulkerson, R., & Johnson, S. (1954).
Solution of a large-scale traveling-salesman problem.
Journal of the operations research society of America, 2(4), 393-410.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("TSP")
    
    n_nodes = 6
    nodes = list(range(n_nodes))
    
    # Dummy distance matrix
    distance = {(i, j): abs(i - j) * 2 + (i * j) % 3 for i in nodes for j in nodes if i != j}
    
    # Variables
    x = {}
    for i in nodes:
        for j in nodes:
            if i != j:
                x[i, j] = model.addVar(vtype="B", name=f"x_{i}_{j}")
                
    u = {}
    for i in range(1, n_nodes):
        u[i] = model.addVar(vtype="C", lb=1, ub=n_nodes-1, name=f"u_{i}")
        
    # Objective
    model.setObjective(quicksum(distance[i, j] * x[i, j] for i in nodes for j in nodes if i != j), "minimize")
    
    # Degree constraints
    for i in nodes:
        model.addCons(quicksum(x[i, j] for j in nodes if i != j) == 1, name=f"out_degree_{i}")
        model.addCons(quicksum(x[j, i] for j in nodes if i != j) == 1, name=f"in_degree_{i}")
        
    if infeasible:
        model.addCons(quicksum(x[i, j] for i in nodes for j in nodes if i != j) <= 2, name="inf_cons")
        
    # Subtour elimination
    for i in range(1, n_nodes):
        for j in range(1, n_nodes):
            if i != j:
                model.addCons(u[i] - u[j] + (n_nodes - 1) * x[i, j] <= n_nodes - 2, name=f"sec_{i}_{j}")
                
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
