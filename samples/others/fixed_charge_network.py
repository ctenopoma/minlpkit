"""固定費用付きネットワークフロー問題 (Fixed Charge Network Flow Problem)

事業ストーリー
--------------
物流ネットワーク設計担当者が、複数の配送センター・中継拠点・最終拠点からなる
ネットワーク上で、どの輸送ルート(リンク)を開設し、それぞれにどれだけの物量を
流すかを決める問題である。各リンクを使うと(トラック便の契約・専用線の敷設など)
固定費用が発生し、さらに実際に運ぶ物量に比例した変動輸送費用もかかる。
リンクには積載能力上限があるため、需要をすべて満たすには複数拠点を経由する
迂回ルートも組み合わせる必要があり、「固定費を払ってでも短絡ルートを開くべきか、
既存の迂回路の変動費を積み増すべきか」というトレードオフが設計の核心となる。

各制約の業務的意味:
- **リンク容量とリンク開設の連動**: リンクを開設(固定費用発生)しない限り、
  そのリンクに物量を流すことはできない(輸送契約を結ばなければトラックは動かせない)。
- **容量上限**: 開設したリンクでも、車両台数・回線容量による輸送上限がある。
- **フロー保存則**: 各拠点で「流入-流出」が需給量と一致しなければならない
  (発生した需要は必ずどこかから満たされ、供給地からの出荷は在庫と整合する)。

(元の学術的定式化: Magnanti, T. L., & Wong, R. T. (1984). Network design and
transportation planning: Models and algorithms. Transportation science.)
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("FixedChargeNetwork")

    # 拠点: 1,2=供給拠点(工場) 3,4,5=中継拠点(ハブ倉庫) 6,7,8=需要拠点(販売店)
    nodes = [1, 2, 3, 4, 5, 6, 7, 8]

    edges = [
        (1, 3), (1, 4), (2, 4), (2, 5),          # 供給拠点 -> 中継拠点
        (3, 4), (4, 5),                          # 中継拠点間の横持ち
        (3, 6), (3, 7), (4, 6), (4, 7), (4, 8), (5, 7), (5, 8),  # 中継拠点 -> 需要拠点
    ]

    fixed_cost = {
        (1, 3): 400, (1, 4): 550, (2, 4): 480, (2, 5): 420,
        (3, 4): 150, (4, 5): 160,
        (3, 6): 300, (3, 7): 320, (4, 6): 280, (4, 7): 260, (4, 8): 340,
        (5, 7): 310, (5, 8): 290,
    }
    variable_cost = {
        (1, 3): 3.0, (1, 4): 4.0, (2, 4): 3.5, (2, 5): 3.0,
        (3, 4): 1.5, (4, 5): 1.5,
        (3, 6): 2.5, (3, 7): 2.8, (4, 6): 2.2, (4, 7): 2.0, (4, 8): 2.6,
        (5, 7): 2.4, (5, 8): 2.1,
    }
    capacity = {
        (1, 3): 60, (1, 4): 55, (2, 4): 50, (2, 5): 60,
        (3, 4): 40, (4, 5): 40,
        (3, 6): 35, (3, 7): 30, (4, 6): 35, (4, 7): 30, (4, 8): 35,
        (5, 7): 30, (5, 8): 35,
    }

    # 供給拠点は正、需要拠点は負、中継拠点は0(フロー保存則の右辺)
    if infeasible:
        supply = {1: 90, 2: 90, 3: 0, 4: 0, 5: 0, 6: -50, 7: -50, 8: -50}  # 総需要を大幅超過
    else:
        supply = {1: 55, 2: 50, 3: 0, 4: 0, 5: 0, 6: -35, 7: -38, 8: -32}

    x = {}
    y = {}

    for i, j in edges:
        x[i, j] = model.addVar(vtype="C", name=f"flow_{i}_{j}", lb=0)
        y[i, j] = model.addVar(vtype="B", name=f"use_{i}_{j}")

    for i, j in edges:
        model.addCons(x[i, j] <= capacity[i, j] * y[i, j], name=f"capacity_{i}_{j}")

    for n in nodes:
        inflow = quicksum(x[i, j] for i, j in edges if j == n)
        outflow = quicksum(x[i, j] for i, j in edges if i == n)
        model.addCons(outflow - inflow == supply.get(n, 0), name=f"flow_conservation_{n}")

    model.setObjective(quicksum(fixed_cost[i, j] * y[i, j] + variable_cost[i, j] * x[i, j] for i, j in edges), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
