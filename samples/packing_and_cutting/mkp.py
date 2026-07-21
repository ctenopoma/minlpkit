"""複数資源制約下のプロジェクト選定問題 (Multidimensional Knapsack Problem, MKP)

事業ストーリー
--------------
研究開発部門の投資判断担当者が、複数の候補プロジェクト(新製品開発案件)の中から、
予算・人員(エンジニア工数)・実験設備の稼働時間といった複数種類の限られた経営資源を
同時に消費する制約の下で、期待収益の合計が最大になるように採否(実施する/しない)を
決める問題である。単純な予算制約だけのナップサック問題と異なり、実際のプロジェクト
選定では「予算は足りても人員が足りない」「人員は足りても実験設備の空きがない」
といった複数のボトルネック資源が同時に効くため、資源ごとの制約をすべて満たす
組合せを見つける必要がある。

各制約の業務的意味:
- **資源制約(予算・人員・設備の各次元)**: 選定したプロジェクトが消費する各資源の
  合計が、その資源の利用可能量(部門予算、確保できるエンジニア数、設備の年間稼働
  時間)を超えてはならない。1つでも超過すれば実行不可能な計画になる。
- **採否は二値**: プロジェクトは部分的に実施することができない
  (途中でやめれば投資が回収できない一括投資の性質)。

(元の学術的定式化: Weingartner, H. M., & Ness, D. N. (1967). Methods for the
solution of the multidimensional 0/1 knapsack problem. Operations Research.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("MKP")

    # 12件の候補プロジェクトと期待収益 [百万円]
    items = 12
    values = [50, 40, 30, 20, 60, 45, 55, 35, 25, 48, 38, 58]

    # 4種類の資源: 予算[百万円]、エンジニア工数[人月]、実験設備[稼働時間]、外部委託費[百万円]
    resources = 4
    weights = [
        [12, 5, 8, 3, 15, 10, 14, 6, 4, 11, 9, 16],   # 予算
        [8, 10, 5, 6, 9, 7, 11, 4, 5, 8, 6, 12],       # エンジニア工数
        [5, 4, 12, 7, 8, 6, 9, 3, 5, 10, 7, 11],       # 実験設備
        [6, 8, 4, 5, 10, 9, 7, 6, 3, 8, 5, 9],         # 外部委託費
    ]
    capacities = [55, 40, 42, 38]

    if infeasible:
        capacities = [5, 5, 5, 5]  # 予算・人員がほぼゼロでは1件も選べず矛盾する下限制約を追加

    # 変数: プロジェクトiを実施するなら1
    x = {}
    for i in range(items):
        x[i] = model.addVar(vtype="B", name=f"x_{i}")

    # 資源制約
    for r in range(resources):
        model.addCons(quicksum(weights[r][i] * x[i] for i in range(items)) <= capacities[r], name=f"capacity_{r}")

    if infeasible:
        model.addCons(quicksum(x[i] for i in range(items)) >= items + 1, name="inf_constraint")

    # 目的関数: 期待収益合計の最大化
    model.setObjective(quicksum(values[i] * x[i] for i in range(items)), "maximize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
