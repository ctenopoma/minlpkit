"""線形化二次割当問題 (QAP) — Linearized Quadratic Assignment Problem

事業ストーリー
--------------
工場レイアウト設計担当者が、複数の生産設備(機械・工程)を工場内の候補設置場所に
割り当てる際、設備間で行き来する部材・仕掛品の物流量(フロー)と設置場所間の
物理的な距離の積(=搬送コスト)の総和を最小化する。設備間フローと拠点間距離を
同時に考慮する必要があるため目的関数が本質的に二次(割当変数の積)になり、
Adams-Johnson法で線形化してMIPとして解く。

各制約の業務的意味:
- **assign_fac / assign_loc**: 各設備は必ずどこか1つの場所に設置し、各場所には
  必ず1つの設備しか置けない(1対1の割当制約)。
- **lin(線形化)**: 補助変数y[i,k,j,l]が「設備iを場所kに、かつ設備jを場所lに
  同時に割り当てる」という二値変数の積を表すことを、線形制約で強制する
  (Adams-Johnson線形化)。
- **sym**: y[i,k,j,l]とy[j,l,i,k]は同一のペア割当を表すため値が一致する
  という対称性を明示し、冗長な変数・制約を減らす。

参考文献: Koopmans, T. C., & Beckmann, M. (1957). Assignment problems and the
location of economic activities. Econometrica.
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("QAPLinearized")
    
    # Dummy data
    n = 3
    flow = [
        [0, 5, 2],
        [5, 0, 3],
        [2, 3, 0]
    ]
    dist = [
        [0, 10, 20],
        [10, 0, 15],
        [20, 15, 0]
    ]
    
    # Variables
    x = {} # x[i, k] = 1 if facility i is assigned to location k
    y = {} # y[i, k, j, l] = x[i, k] * x[j, l]
    
    for i in range(n):
        for k in range(n):
            x[i, k] = model.addVar(vtype="B", name=f"x_{i}_{k}")
            for j in range(n):
                for l in range(n):
                    if i != j and k != l:
                        y[i, k, j, l] = model.addVar(vtype="C", lb=0, name=f"y_{i}_{k}_{j}_{l}")
                        
    # Constraints
    # Assignment
    for i in range(n):
        model.addCons(quicksum(x[i, k] for k in range(n)) == 1, name=f"assign_fac_{i}")
    for k in range(n):
        model.addCons(quicksum(x[i, k] for i in range(n)) == 1, name=f"assign_loc_{k}")
        
    # Linearization
    for i in range(n):
        for k in range(n):
            for j in range(n):
                if i != j:
                    model.addCons(quicksum(y[i, k, j, l] for l in range(n) if l != k) == x[i, k], name=f"lin_{i}_{k}_{j}")
                    
    # Symmetry
    for i in range(n):
        for k in range(n):
            for j in range(n):
                for l in range(n):
                    if i != j and k != l and i < j:
                        model.addCons(y[i, k, j, l] == y[j, l, i, k], name=f"sym_{i}_{k}_{j}_{l}")
                        
    if infeasible:
        model.addCons(x[0, 0] + x[0, 1] + x[0, 2] == 0, name="inf_constraint")
        
    # Objective
    model.setObjective(quicksum(flow[i][j] * dist[k][l] * y[i, k, j, l] 
                                for i in range(n) for k in range(n) 
                                for j in range(n) for l in range(n) if i != j and k != l), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
