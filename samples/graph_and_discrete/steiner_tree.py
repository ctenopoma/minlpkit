"""シュタイナー木問題 (MIP) — Steiner Tree Problem in Graphs

事業ストーリー
--------------
通信キャリアのネットワーク敷設担当者が、複数の拠点(データセンターや基地局など
必ず接続しなければならない「端点」)をすべて接続する光ファイバー網を、
敷設コスト(距離・工事費)最小で設計する。端点以外の中継ノードを経由してもよいが、
経由すること自体には追加コストが乗らず、実際に敷設した回線(エッジ)のコストのみが
かかるため、端点だけを直接結ぶ木より安く済む場合がある(これがシュタイナー木問題)。

各制約の業務的意味:
- **flow_cons(多端末フロー保存)**: 各端点tについて、根ノードから1単位の
  仮想フローを流し、端点tでちょうど吸収されるようにする。これにより
  「根から各端点まで経路が存在する=接続されている」ことを保証する。
- **cap(容量制約)**: 仮想フローは、実際に回線(エッジ)を敷設した(y=1)区間
  にしか流せない。これにより、フローが通る経路が必ず実際の配線として
  選択されることを強制する。
- **目的関数**: 実際に敷設するエッジの総コスト(距離・工事費)を最小化する。

参考文献: Hwang, F. K., Richards, D. S., & Winter, P. (1992). The Steiner tree
problem. Elsevier.
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("SteinerTree")
    
    nodes = [1, 2, 3, 4, 5, 6]
    terminals = [1, 3, 6]
    root = terminals[0]
    
    edges = [(1, 2), (2, 3), (1, 4), (4, 5), (5, 6), (2, 5), (3, 6)]
    costs = {(1, 2): 2, (2, 3): 2, (1, 4): 10, (4, 5): 10, (5, 6): 10, (2, 5): 1, (3, 6): 2}
    
    if infeasible:
        edges = [(1, 2), (2, 3), (1, 4), (4, 5)] # 6 is disconnected
        costs = {(1, 2): 2, (2, 3): 2, (1, 4): 10, (4, 5): 10}
        
    # Bidirectional edges for flow
    arcs = []
    for u, v in edges:
        arcs.append((u, v))
        arcs.append((v, u))
        
    y = {}
    for u, v in edges:
        y[u, v] = model.addVar(vtype="B", name=f"edge_{u}_{v}")
        
    x = {}
    for t in terminals:
        if t != root:
            for u, v in arcs:
                x[t, u, v] = model.addVar(vtype="C", name=f"flow_{t}_{u}_{v}", lb=0)
                
    for t in terminals:
        if t != root:
            for n in nodes:
                inflow = quicksum(x[t, i, j] for i, j in arcs if j == n)
                outflow = quicksum(x[t, i, j] for i, j in arcs if i == n)
                
                if n == root:
                    demand = 1
                elif n == t:
                    demand = -1
                else:
                    demand = 0
                    
                model.addCons(outflow - inflow == demand, name=f"flow_cons_{t}_{n}")
                
            for u, v in arcs:
                # Flow can only go if edge is selected
                edge_var = y[u, v] if (u, v) in edges else y[v, u]
                model.addCons(x[t, u, v] <= edge_var, name=f"cap_{t}_{u}_{v}")
                
    model.setObjective(quicksum(costs[u, v] * y[u, v] for u, v in edges), "minimize")
    
    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
