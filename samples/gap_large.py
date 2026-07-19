"""大規模一般化割当問題 GAP (MILP) — GPU primal heuristics の検証用

各タスクをちょうど1エージェントに割り当て、容量制約下で費用最小化する。
容量をタイトにすると「可行解を見つけること自体」がNP困難になり、
Feasibility Jump 系のGPUヒューリスティクス(cuOpt等)が効きやすい構造
(等式制約 + ナップサック容量、巨大バイナリ、木探索より一括評価向き)を持つ。

    min  Σ_ij c[i,j]·x[i,j]
    s.t. Σ_j x[i,j] = 1        (各タスクはちょうど1エージェント)
         Σ_i r[i,j]·x[i,j] <= b[j]  (エージェント容量)

インスタンスは Yagiura らのタイプD類似(費用と資源が逆相関で難しい)。
scale: small=200x10(テスト用) / large=1500x50 / xl=3000x80

実行: uv run python samples/gap_large.py [scale]
"""

from __future__ import annotations

import random

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_tasks=200, n_agents=10, tightness=0.97, seed=42),
    "large": dict(n_tasks=1500, n_agents=50, tightness=0.96, seed=42),
    "xl": dict(n_tasks=3000, n_agents=80, tightness=0.95, seed=42),
}


def make_instance(n_tasks: int, n_agents: int, tightness: float, seed: int):
    """タイプD類似: r~U(1,100)、c = 111 - r + ノイズ(費用最小化と容量充足が競合)。"""
    rng = random.Random(seed)
    r = [[rng.randint(1, 100) for _ in range(n_agents)] for _ in range(n_tasks)]
    c = [[max(1, 111 - r[i][j] + rng.randint(-10, 10)) for j in range(n_agents)]
         for i in range(n_tasks)]
    # 容量: 平均負荷 × tightness(タイトなほど可行解発見が難しい)
    avg_load = sum(sum(row) for row in r) / (n_agents * n_agents)
    b = [int(avg_load * tightness) for _ in range(n_agents)]
    return r, c, b


def build_model(scale: str = "large") -> Model:
    cfg = SCALES[scale]
    r, c, b = make_instance(cfg["n_tasks"], cfg["n_agents"], cfg["tightness"], cfg["seed"])
    n, a = cfg["n_tasks"], cfg["n_agents"]

    m = Model(f"gap_{scale}")
    x = {(i, j): m.addVar(vtype="B", name=f"x_{i}_{j}") for i in range(n) for j in range(a)}
    for i in range(n):
        m.addCons(quicksum(x[i, j] for j in range(a)) == 1, name=f"assign_{i}")
    for j in range(a):
        m.addCons(quicksum(r[i][j] * x[i, j] for i in range(n)) <= b[j], name=f"cap_{j}")
    m.setObjective(quicksum(c[i][j] * x[i, j] for i in range(n) for j in range(a)), "minimize")
    m.data = dict(x=x, n=n, a=a)
    return m


def main() -> None:
    import sys
    scale = sys.argv[1] if len(sys.argv) > 1 else "large"
    m = build_model(scale)
    m.setParam("limits/time", 120)
    m.optimize()
    print(f"status={m.getStatus()}  sols={m.getNSols()}  "
          f"obj={m.getObjVal():,.0f}" if m.getNSols() else "no solution",
          f"gap={m.getGap() * 100:.2f}%  nodes={m.getNNodes()}  time={m.getSolvingTime():.1f}s")


if __name__ == "__main__":
    main()
