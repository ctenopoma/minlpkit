"""カーディナリティ制約付きポートフォリオ最適化 (Portfolio Optimization with Cardinality Constraints)

事業ストーリー
--------------
資産運用会社のポートフォリオマネージャーが、複数の候補銘柄(株式・債券・REIT等)の
中から、実際に管理・監視できる銘柄数の上限(カーディナリティ)を守りながら、
期待リターンを最大化する投資配分を決める問題である。理論上はより多くの銘柄に
分散するほどリスク低減に有利だが、実務では銘柄ごとにモニタリングコスト・取引手数料
・最低取引ロットが発生するため、運用チームが同時に追える銘柄数には現実的な上限がある。
また一度組み入れると決めた銘柄には最低投資比率(ポジションとして意味のある規模)と
最大投資比率(集中リスク抑制)の両方が課される。

各制約の業務的意味:
- **投資比率の合計=100%**: 運用資金全額を配分する(現金として遊ばせない)。
- **組入銘柄数の上限(カーディナリティ)**: モニタリング・取引コストの制約から
  同時に保有できる銘柄数を制限する。
- **最低/最大投資比率**: 組み入れた銘柄には意味のある規模で投資する下限
  (小さすぎるポジションは分散効果より取引コストが上回る)と、1銘柄への
  集中リスクを避けるための上限を両方課す。
- **セクター配分上限**: 特定セクターへの偏りによる集中リスクを避けるため、
  セクターごとの投資比率合計に上限を設ける。

(元の学術的定式化: Bienstock, D. (1996). Computational study of a family of
mixed-integer quadratic programming problems. Mathematical programming.)
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("PortfolioMIP")

    # 12銘柄の候補(期待リターンとセクター分類)
    assets = list(range(1, 13))
    returns = {
        1: 0.045, 2: 0.052, 3: 0.061, 4: 0.038, 5: 0.070,
        6: 0.048, 7: 0.083, 8: 0.055, 9: 0.066, 10: 0.041,
        11: 0.058, 12: 0.075,
    }
    sector = {
        1: "Tech", 2: "Tech", 3: "Tech",
        4: "Finance", 5: "Finance", 6: "Finance",
        7: "Energy", 8: "Energy",
        9: "Healthcare", 10: "Healthcare",
        11: "Consumer", 12: "Consumer",
    }
    sectors = sorted(set(sector.values()))
    sector_cap = 0.40  # 1セクターへの投資比率上限

    min_invest = 0.05
    max_invest = 0.25
    cardinality = 6  # 同時に保有できる銘柄数の上限

    if infeasible:
        min_invest = 0.30  # cardinality銘柄でも合計が100%を超え実行不能になる

    x = {}  # 投資比率
    z = {}  # 組入の有無(バイナリ)

    for i in assets:
        x[i] = model.addVar(vtype="C", name=f"weight_{i}", lb=0, ub=1)
        z[i] = model.addVar(vtype="B", name=f"include_{i}")

    model.addCons(quicksum(x[i] for i in assets) == 1.0, name="total_weight")

    for i in assets:
        model.addCons(x[i] >= min_invest * z[i], name=f"min_inv_{i}")
        model.addCons(x[i] <= max_invest * z[i], name=f"max_inv_{i}")

    model.addCons(quicksum(z[i] for i in assets) <= cardinality, name="cardinality_limit")

    for s in sectors:
        model.addCons(
            quicksum(x[i] for i in assets if sector[i] == s) <= sector_cap,
            name=f"sector_cap_{s}",
        )

    model.setObjective(quicksum(returns[i] * x[i] for i in assets), "maximize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
