"""R&D新規事業投資ポートフォリオ (R&D Project Portfolio)

事業ストーリー
--------------
研究開発部門の「R&D投資委員会」が、複数年度にわたる研究開発予算配分を決める意思決定
である。各プロジェクトは複数年度(フェーズ)にわたって段階的に投資が必要で、年度ごとの
予算上限を超えてはならない。また一部プロジェクトは技術的な前提関係(先行研究への
投資が完了していないと後続フェーズに着手できない)を持つ。委員会は、限られた年度予算の
下で採択するプロジェクト群(0/1の採否判断)を決め、期待リターンの合計を最大化する。
前提関係を整数変数間の論理制約として表すことで、実際の研究開発ポートフォリオが持つ
「段階投資」「技術的従属」という構造を単純な0/1ナップサックから拡張している。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_project=5, n_year=2),
    "default": dict(n_project=8, n_year=3),
    "large": dict(n_project=12, n_year=3),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_project, n_year = cfg["n_project"], cfg["n_year"]
    projects = range(n_project)
    years = range(n_year)

    # 年度別投資額(プロジェクトごとに規模・投資期間が異なる)
    cost = {(i, y): 30 + 10 * ((i + y) % 5) for i in projects for y in years}
    returns = [150 + 40 * (i % 4) for i in projects]
    budget = {y: 120 + 15 * y for y in years}  # 年度が進むほど予算がやや拡大

    model = Model("RD_Project_Portfolio")

    select = {i: model.addVar(vtype="B", name=f"select_{i}") for i in projects}

    for y in years:
        model.addCons(
            quicksum(select[i] * cost[i, y] for i in projects) <= budget[y], name=f"budget_{y}")

    # 技術的前提関係: プロジェクト i+1 は i の採択を前提とする(隣接ペアの一部に設定)
    for i in range(0, n_project - 1, 3):
        model.addCons(select[i + 1] <= select[i], name=f"prereq_{i}_{i+1}")

    # 総プロジェクト数の上限(委員会がレビューできる件数の現実的な制約)
    model.addCons(quicksum(select[i] for i in projects) <= max(3, n_project // 2), name="portfolio_size")

    model.setObjective(quicksum(select[i] * returns[i] for i in projects), "maximize")
    model.data = {"select": select, "dims": (n_project, n_year)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Total Return:", m.getObjVal())
