"""大規模集合分割問題 (MILP) — GPU primal heuristics の検証用

乗務員ペアリング等の原型。要素全体をちょうど1回ずつ覆う列の組合せを費用最小で選ぶ。
等式被覆制約のため可行解発見自体が難しく(LP緩和は解けても整数可行解が遠い)、
cuOpt 論文 (arXiv:2510.20499) や Feasibility Jump 論文でGPU/FJ系が
強みを示す典型構造。列数を増やしてもモデルは疎なまま巨大化する。

    min  Σ_k cost[k]·x[k]
    s.t. Σ_{k: e∈col[k]} x[k] = 1   (各要素はちょうど1列で覆う)

可行性を保証するため、ランダム分割由来の「植え込み解」列を混ぜる。
scale: small=300要素x3k列 / large=2000要素x40k列 / xl=4000要素x100k列

実行: uv run python samples/set_partitioning.py [scale]
"""

from __future__ import annotations

import random

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_elems=300, n_cols=3000, seed=7),
    "large": dict(n_elems=2000, n_cols=40000, seed=7),
    "xl": dict(n_elems=4000, n_cols=100000, seed=7),
}


def make_instance(n_elems: int, n_cols: int, seed: int):
    """列 = 要素の部分集合(サイズ5-15)。植え込み分割を数本混ぜて可行性を保証。"""
    rng = random.Random(seed)
    cols: list[tuple[frozenset[int], int]] = []

    # 植え込み解: 全要素のランダム分割を3セット(どれか1つで必ず可行)
    for _ in range(3):
        perm = list(range(n_elems))
        rng.shuffle(perm)
        i = 0
        while i < n_elems:
            size = rng.randint(5, 15)
            block = frozenset(perm[i:i + size])
            cols.append((block, len(block) * rng.randint(8, 14)))
            i += size

    # 残りはランダム列(費用は小さめ=選びたくなるが組合せが合わない)
    while len(cols) < n_cols:
        size = rng.randint(5, 15)
        block = frozenset(rng.sample(range(n_elems), size))
        cols.append((block, len(block) * rng.randint(5, 12)))
    return cols


def build_model(scale: str = "large") -> Model:
    cfg = SCALES[scale]
    cols = make_instance(cfg["n_elems"], cfg["n_cols"], cfg["seed"])
    n_elems = cfg["n_elems"]

    m = Model(f"setpart_{scale}")
    x = [m.addVar(vtype="B", name=f"x_{k}") for k in range(len(cols))]
    covering: dict[int, list] = {e: [] for e in range(n_elems)}
    for k, (block, _) in enumerate(cols):
        for e in block:
            covering[e].append(x[k])
    for e in range(n_elems):
        m.addCons(quicksum(covering[e]) == 1, name=f"cover_{e}")
    m.setObjective(quicksum(cost * x[k] for k, (_, cost) in enumerate(cols)), "minimize")
    m.data = dict(x=x, n_cols=len(cols))
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
