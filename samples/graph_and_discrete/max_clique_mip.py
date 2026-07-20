"""最大クリーク問題 (MIP定式化) — Maximum Clique Problem

事業ストーリー
--------------
人事部門のプロジェクトチーム編成担当者が、社員間の「過去プロジェクトでの
協業実績あり(相性が良い)」関係を表すグラフから、全員同士が互いに良好な
関係にある最大のグループ(クリーク)を見つけ、新規プロジェクトのコアチーム
候補として推薦する。

各制約の業務的意味:
- **No_Edge**: 協業実績のない(相性が未確認の)社員ペアを同時にチームへ
  採用すると連携不全のリスクがあるため、そのようなペアを同時に選ばない
  制約を課す。

参考文献: Bomze, I. M., Budinich, M., Pardalos, P. M., & Pelillo, M. (1999).
The maximum clique problem. Handbook of Combinatorial Optimization, 1-74.
"""

import random

from pyscipopt import Model


def make_graph(n: int, p: float, seed: int) -> list[tuple[int, int]]:
    """社員間の過去の協業実績(相性の良さ)を表すランダムグラフ。"""
    rng = random.Random(seed)
    return [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]


def build_model(infeasible=False):
    m = Model("Max_Clique")

    V = 14  # チーム編成候補の社員14名
    edges = make_graph(V, 0.6, seed=3)  # 協業実績あり=辺

    if infeasible:
        m.addCons(0 == 1, name="Infeasible_Cons")  # Force infeasibility

    # Build adjacency matrix
    adj = {i: set() for i in range(V)}
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)

    # Variables
    x = {}
    for i in range(V):
        x[i] = m.addVar(vtype="B", name=f"x_{i}")

    # Objective: Maximize clique size (minimize -size)
    m.setObjective(sum(-x[i] for i in range(V)), "minimize")

    # Constraints: If i and j are not connected, they cannot both be in the clique
    for i in range(V):
        for j in range(i + 1, V):
            if j not in adj[i]:
                m.addCons(x[i] + x[j] <= 1, name=f"No_Edge_{i}_{j}")

    m.data = dict(x=x, edges=edges)
    return m


def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value (Max Clique Size):", -m.getObjVal())
    else:
        print("Status:", m.getStatus())


if __name__ == "__main__":
    main()
