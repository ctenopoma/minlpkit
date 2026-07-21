"""集合被覆問題 (MIP) — Set Cover Problem

事業ストーリー
--------------
市の消防局配置計画担当者が、市内15地区すべてを緊急対応カバー範囲に収める
ために、候補となる消防署設置場所(候補地ごとにカバーできる地区の組合せが
異なる)の中から最小限の署数を選んで開設する。開設・維持コストを抑えつつ、
対応漏れの地区が出ないようにする。

各制約の業務的意味:
- **Cover**: 各地区は必ずどこか1つ以上の消防署でカバーされる(対応漏れの
  地区があると火災・救急時の到着時間が確保できず住民の安全に関わる)。
- **目的関数(開設署数の最小化)**: 開設・人員配置コストを抑えるため、
  必要最小限の署数に絞り込む。

参考文献: Karp, R. M. (1972). Reducibility among combinatorial problems.
In Complexity of Computer Computations (pp. 85-103). Springer, Boston, MA.
"""

from pyscipopt import Model


def build_model(infeasible=False):
    m = Model("Set_Cover")

    universe = list(range(1, 16))  # 市内15地区
    sets = {
        "S1": [1, 2, 3, 4, 5],    # 候補地A(市街中心部をカバー)
        "S2": [3, 4, 6, 7],       # 候補地B
        "S3": [5, 6, 8, 9, 10],   # 候補地C
        "S4": [1, 9, 10, 11],     # 候補地D
        "S5": [2, 7, 11, 12],     # 候補地E
        "S6": [8, 12, 13, 14],    # 候補地F
        "S7": [4, 13, 15],        # 候補地G
        "S8": [10, 14, 15],       # 候補地H
        "S9": [1, 6, 12],         # 候補地I
        "S10": [3, 9, 15],        # 候補地J
    }

    if infeasible:
        sets = {"S1": [1]}  # 2〜15地区をカバーできない=実行不可能な候補地案

    # Variables
    x = {}
    for s_name in sets.keys():
        x[s_name] = m.addVar(vtype="B", name=f"x_{s_name}")

    # Objective
    m.setObjective(sum(x[s] for s in sets.keys()), "minimize")

    # Constraints
    for e in universe:
        covering_sets = [s for s, elements in sets.items() if e in elements]
        m.addCons(sum(x[s] for s in covering_sets) >= 1, name=f"Cover_{e}")

    m.data = dict(x=x, sets=sets)
    return m


def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value:", m.getObjVal())
    else:
        print("Status:", m.getStatus())


if __name__ == "__main__":
    main()
