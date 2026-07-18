"""0-1 ナップサック (MILP) — 被約コスト固定の実証用

強相関(value_i ≈ weight_i + 定数)にすると LP緩和と整数最適のギャップが小さく、
被約コスト固定が効きやすい古典的な難所になる。

    max  Σ v_i x_i   s.t. Σ w_i x_i <= C,  x_i∈{0,1}

被約コスト固定: LP緩和の被約コスト r_i について r_i > (最適値上界−下界) なら x_i を固定できる。
SCIPは redcost 伝播器(既定ON)でこれを自動実施する。
"""

from __future__ import annotations

import random

from pyscipopt import Model, quicksum

N = 45


def make_items(seed: int = 3) -> list[tuple[int, int]]:
    rng = random.Random(seed)
    items = []
    for _ in range(N):
        w = rng.randint(20, 60)
        v = w + rng.randint(8, 12)  # 強相関(value≈weight+小定数)
        items.append((w, v))
    return items


ITEMS = make_items(3)
CAP = int(0.5 * sum(w for w, _ in ITEMS))  # 容量=総重量の半分(タイト)


def build_model() -> Model:
    m = Model("knapsack")
    x = {i: m.addVar(vtype="B", name=f"x_{i}") for i in range(N)}
    m.addCons(quicksum(ITEMS[i][0] * x[i] for i in range(N)) <= CAP, name="capacity")
    m.setObjective(quicksum(ITEMS[i][1] * x[i] for i in range(N)), "maximize")
    m.data = dict(x=x)
    return m


def main() -> None:
    for redcost in (True, False):
        m = build_model()
        m.hideOutput()
        if not redcost:
            m.setParam("propagating/redcost/freq", -1)  # 被約コスト伝播器を無効化
        m.setParam("limits/time", 60)
        m.optimize()
        print(f"redcost={redcost!s:5}: obj={m.getObjVal():.0f} nodes={m.getNNodes()} "
              f"time={m.getSolvingTime():.2f}s")


if __name__ == "__main__":
    main()
