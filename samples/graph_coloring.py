"""グラフ彩色 (MILP) — 対称性除去の実証用

隣接頂点を異色で塗り、使う色数を最小化する。色は完全に入替可能なので
K!個の色置換対称性を持つ(対称性除去が真に効く典型題材)。

    min  Σ_c w_c
    s.t. Σ_c x[v,c] = 1                 (各頂点は1色)
         x[u,c] + x[v,c] <= 1  ((u,v)∈E) (隣接は異色)
         x[v,c] <= w_c                   (使った色にフラグ)

symmetry_break=True で色対称性を除去:
    w_c >= w_{c+1}                       (小さい色から使う)
    x[v,c] = 0  for c > v                (頂点vは色1..v+1のみ=代表元固定)
"""

from __future__ import annotations

import random

from pyscipopt import Model, quicksum


def make_graph(n: int = 11, p: float = 0.5, seed: int = 7) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    return [(u, v) for u in range(n) for v in range(u + 1, n) if rng.random() < p]


N = 11
K = 6  # 最大色数
EDGES = make_graph(N, 0.5, 7)


def build_model(symmetry_break: bool = False) -> Model:
    m = Model("graph_coloring")
    x = {(v, c): m.addVar(vtype="B", name=f"x_{v}_{c}") for v in range(N) for c in range(K)}
    w = {c: m.addVar(vtype="B", name=f"w_{c}") for c in range(K)}

    for v in range(N):
        m.addCons(quicksum(x[v, c] for c in range(K)) == 1, name=f"assign_{v}")
    for (u, v) in EDGES:
        for c in range(K):
            m.addCons(x[u, c] + x[v, c] <= 1, name=f"edge_{u}_{v}_{c}")
    for v in range(N):
        for c in range(K):
            m.addCons(x[v, c] <= w[c], name=f"use_{v}_{c}")

    if symmetry_break:
        for c in range(K - 1):
            m.addCons(w[c] >= w[c + 1], name=f"worder_{c}")
        # 頂点vは色0..min(v,K-1)のみ(代表元固定で色対称性を除去)
        for v in range(N):
            for c in range(v + 1, K):
                m.addCons(x[v, c] == 0, name=f"symbreak_{v}_{c}")

    m.setObjective(quicksum(w[c] for c in range(K)), "minimize")
    m.data = dict(x=x, w=w)
    return m


def main() -> None:
    # 2x2: SCIP内蔵対称性 on/off × 明示的除去 on/off
    for scip_sym in (True, False):
        for sb in (False, True):
            m = build_model(symmetry_break=sb)
            m.hideOutput()
            m.setParam("misc/usesymmetry", 1 if scip_sym else 0)
            m.setParam("limits/time", 60)
            m.optimize()
            print(f"scip_sym={scip_sym!s:5} break={sb!s:5}: colors={m.getObjVal():.0f} "
                  f"nodes={m.getNNodes()} time={m.getSolvingTime():.2f}s")


if __name__ == "__main__":
    main()
