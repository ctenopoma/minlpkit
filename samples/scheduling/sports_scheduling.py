"""スポーツリーグの試合日程編成 (Sports Scheduling Problem)

事業ストーリー
--------------
地域バスケットボールリーグの運営担当者が、4チームによるシングルラウンドロビン
(総当たり戦を1回ずつ)の試合日程を組む。全チームが週に1試合ずつ、他の全チームと
ちょうど1回対戦するように組み合わせと開催週を決める必要がある。アウェーチームの
移動距離が長いほど遠征コスト・選手の疲労が増えるため、リーグ全体の総移動距離
(アウェー側の移動)を最小化する日程を編成する。

各制約の業務的意味:
- **週1試合の制約**: 各チームは各週にちょうど1試合(ホームまたはアウェー)を行う
  (同週に2試合を組むと選手の休養が確保できない)。
- **総当たり制約**: 各チームの組は、リーグ全期間を通じてちょうど1回対戦する
  (同じ対戦を2度組んだり、対戦しないまま終わるのを防ぐ)。
- **総移動距離最小化**: アウェーチームの移動距離の合計を最小化し、遠征コストと
  選手の負担を抑える。

(元の学術的定義: Nemhauser and Trick (1998) - Scheduling a major college basketball conference.)
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
