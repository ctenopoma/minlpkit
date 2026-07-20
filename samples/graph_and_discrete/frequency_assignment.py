"""周波数割当問題 (MIP) — Frequency Assignment Problem

事業ストーリー
--------------
移動体通信事業者の無線ネットワーク設計担当者が、市内に設置した基地局(セル)
それぞれに使用する周波数チャネルを割り当てる。近接して電波が干渉し合う基地局
同士に同じ周波数を割り当てると通話品質が劣化するため、干渉が起きる基地局ペア
には異なる周波数を割り当てつつ、使用する周波数番号の最大値(=確保すべき
周波数帯域幅、ライセンス費用に直結)を最小化する。

各制約の業務的意味:
- **one_freq**: 各基地局には必ず1つの周波数チャネルを割り当てる
  (未割当の基地局は運用開始できない)。
- **interference**: 電波干渉が発生する基地局ペアには同一周波数を使わせない
  (通話品質・通信エラー率の悪化を防ぐ)。
- **max_f_def / 目的関数**: 実際に使用する周波数番号の最大値を最小化する
  ことで、確保が必要な周波数帯域幅を抑え、電波利用ライセンスの取得コストを
  下げる。

参考文献: Aardal, K. I., et al. (2007). Models and solution techniques for
frequency assignment problems. Annals of Operations Research.
"""
from __future__ import annotations

import random

from pyscipopt import Model, quicksum


def make_interference_graph(n_links: int, p: float, seed: int) -> list[tuple[int, int]]:
    """基地局間の距離が近いほど電波干渉が起きやすいと仮定したランダム干渉グラフ。"""
    rng = random.Random(seed)
    return [(u, v) for u in range(1, n_links + 1) for v in range(u + 1, n_links + 1) if rng.random() < p]


def build_model(infeasible=False):
    model = Model("FrequencyAssignment")

    n_links = 10  # 市内に設置された基地局数
    links = list(range(1, n_links + 1))
    frequencies = list(range(1, 7))  # 利用可能な周波数チャネル(6本)

    interference_edges = make_interference_graph(n_links, 0.3, seed=11)

    if infeasible:
        frequencies = [1, 2]

    x = {}
    for i in links:
        for f in frequencies:
            x[i, f] = model.addVar(vtype="B", name=f"assign_{i}_{f}")

    # Each link needs exactly one frequency
    for i in links:
        model.addCons(quicksum(x[i, f] for f in frequencies) == 1, name=f"one_freq_{i}")

    # Interference constraints
    for u, v in interference_edges:
        for f in frequencies:
            model.addCons(x[u, f] + x[v, f] <= 1, name=f"interference_{u}_{v}_{f}")

    # Minimize max frequency used
    max_f = model.addVar(vtype="C", name="max_freq")
    for i in links:
        for f in frequencies:
            model.addCons(max_f >= f * x[i, f], name=f"max_f_def_{i}_{f}")

    model.setObjective(max_f, "minimize")
    model.data = dict(x=x, links=links, frequencies=frequencies, interference_edges=interference_edges)

    return model


def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())


if __name__ == "__main__":
    main()
