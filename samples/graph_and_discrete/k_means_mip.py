"""K-meansクラスタリング (MIP定式化) — K-Means Clustering

事業ストーリー
--------------
小売チェーンの物流企画担当者が、各店舗の所在地(座標)を基に、新設する配送
センターをどの店舗に併設するか、また各店舗をどの配送センターの配送エリアに
割り当てるかを同時に決定する。店舗-配送センター間の距離の二乗和を最小化する
ことで、配送ルートの総移動距離・配送コストを抑える(配送センターは既存店舗の
いずれかに併設する前提のk-medoids型のMIP定式化)。

各制約の業務的意味:
- **Num_Clusters**: 新設予算の制約から、配送センターとして選べる店舗数は
  K拠点までに限られる。
- **Assign**: 各店舗は必ずどこか1つの配送センターの配送エリアに紐付ける
  (未割当の店舗には商品を配送できない)。
- **Valid_Center**: 配送センターとして選ばれていない店舗には、他店舗を
  割り当てられない(実在しない拠点への配送はできない)。

参考文献: Aloise, D., Deshpande, A., Hansen, P., & Popat, P. (2009).
NP-hardness of Euclidean sum-of-squares clustering. Machine Learning, 75(2), 245-248.
"""

from pyscipopt import Model


def build_model(infeasible=False):
    m = Model("K-Means_MIP")

    # 3地域(都心・郊外A・郊外B)に分散する12店舗の座標
    points = [
        (0, 0), (1, 1), (2, 0), (1, -1),          # 都心エリア
        (10, 10), (11, 11), (12, 10), (11, 9),    # 郊外Aエリア
        (0, 10), (1, 11), (-1, 10), (0, 9),       # 郊外Bエリア
    ]
    N = len(points)
    K = 3  # 新設できる配送センター数

    if infeasible:
        K = 0  # 配送センターを1つも新設できない=実行不可能な予算制約

    # Variables
    # x[i, j] = 1 if point i is assigned to cluster center j (which is point j)
    x = {}
    for i in range(N):
        for j in range(N):
            x[i, j] = m.addVar(vtype="B", name=f"x_{i}_{j}")

    # y[j] = 1 if point j is chosen as a cluster center
    y = {}
    for j in range(N):
        y[j] = m.addVar(vtype="B", name=f"y_{j}")

    # Objective: minimize sum of squared distances
    obj = 0
    for i in range(N):
        for j in range(N):
            dist_sq = (points[i][0] - points[j][0])**2 + (points[i][1] - points[j][1])**2
            obj += dist_sq * x[i, j]
    m.setObjective(obj, "minimize")

    # Constraints
    # 1. Exactly K centers must be chosen
    m.addCons(sum(y[j] for j in range(N)) == K, name="Num_Clusters")

    # 2. Each point is assigned to exactly one center
    for i in range(N):
        m.addCons(sum(x[i, j] for j in range(N)) == 1, name=f"Assign_{i}")

    # 3. A point can only be assigned to j if j is a center
    for i in range(N):
        for j in range(N):
            m.addCons(x[i, j] <= y[j], name=f"Valid_Center_{i}_{j}")

    m.data = dict(x=x, y=y, points=points)
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
