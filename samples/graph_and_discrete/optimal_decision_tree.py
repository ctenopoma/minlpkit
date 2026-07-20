"""最適決定木 (簡略版MIP) — Optimal Decision Tree

事業ストーリー
--------------
消費者金融の融資審査担当者が、申込者の属性(年収スコア・借入希望額スコア・
既存借入件数スコアの3指標)から「承認/却下」を判定する、深さ1の解釈可能な
決定木ルールをMIPで学習する。複雑なブラックボックスモデルではなく「この指標が
この閾値を超えたら承認」という1本の分岐ルールに絞り込むことで、審査担当者や
監督当局への説明責任を果たしつつ、過去16件の審査結果に対する誤判定を最小化する。

各制約の業務的意味:
- **split_feat**: 分岐に使う指標は必ず1つだけ選ぶ(複数指標を組み合わせた
  複合ルールは解釈性を損なうため禁止)。
- **leaf_class**: 各葉(分岐後のグループ)には必ず1つの判定(承認/却下)を割り当てる。
- **sample_leaf**: 各申込者は必ずどちらか一方の葉に振り分けられる。
- **route_left/route_right(Big-M)**: 分岐変数a・閾値bに基づき、実際の指標値が
  閾値以下なら左の葉、超えれば右の葉に振り分けられることを線形制約で表現する。
- **err**: 振り分け先の葉の判定が実際の承認/却下結果と食い違う件数(誤判定数)
  を最小化する。

参考文献: Bertsimas, D., & Dunn, J. (2017). Optimal classification trees.
Machine Learning.
"""
from pyscipopt import Model, quicksum


def build_model(infeasible=False):
    model = Model("OptimalDecisionTree")

    # Depth 1 tree: 1 root split node (0), 2 leaf nodes (1, 2)
    split_nodes = [0]
    leaf_nodes = [1, 2]

    # 申込者の指標: 0=年収スコア, 1=借入希望額スコア, 2=既存借入件数スコア(いずれも0-1正規化)
    features = [0, 1, 2]

    # (年収スコア, 借入希望額スコア, 既存借入件数スコア, 実際の判定 0=却下/1=承認)
    data = [
        (0.15, 0.20, 0.10, 0),
        (0.85, 0.90, 0.20, 1),
        (0.20, 0.10, 0.30, 0),
        (0.90, 0.80, 0.10, 1),
        (0.10, 0.30, 0.40, 0),
        (0.75, 0.70, 0.15, 1),
        (0.25, 0.15, 0.50, 0),
        (0.95, 0.85, 0.05, 1),
        (0.05, 0.25, 0.60, 0),
        (0.80, 0.75, 0.25, 1),
        (0.30, 0.05, 0.35, 0),
        (0.70, 0.65, 0.30, 1),
        (0.12, 0.18, 0.45, 0),
        (0.88, 0.92, 0.12, 1),
        (0.18, 0.22, 0.55, 0),
        (0.78, 0.68, 0.18, 1),
    ]
    classes = [0, 1]

    if infeasible:
        model.addCons(quicksum(model.addVar(name="dummy_inf") for _ in range(1)) <= -1, name="inf_cons")

    # Variables
    a = {}  # a[t, f] = 1 if feature f is selected at node t
    b = {}  # threshold at node t
    c = {}  # c[t, k] = 1 if leaf t predicts class k
    z = {}  # z[i, t] = 1 if sample i falls into leaf t

    for t in split_nodes:
        b[t] = model.addVar(vtype="C", name=f"b_{t}", lb=0, ub=1)
        for f in features:
            a[t, f] = model.addVar(vtype="B", name=f"a_{t}_{f}")

    for t in leaf_nodes:
        for k in classes:
            c[t, k] = model.addVar(vtype="B", name=f"c_{t}_{k}")

    for i in range(len(data)):
        for t in leaf_nodes:
            z[i, t] = model.addVar(vtype="B", name=f"z_{i}_{t}")

    # Splits must use one feature
    for t in split_nodes:
        model.addCons(quicksum(a[t, f] for f in features) == 1, name=f"split_feat_{t}")

    # Leaf must assign one class
    for t in leaf_nodes:
        model.addCons(quicksum(c[t, k] for k in classes) == 1, name=f"leaf_class_{t}")

    # Sample must fall into exactly one leaf
    for i in range(len(data)):
        model.addCons(quicksum(z[i, t] for t in leaf_nodes) == 1, name=f"sample_leaf_{i}")

    M = 2.0
    eps = 0.001
    for i, row in enumerate(data):
        x_vals = row[:-1]
        expr = quicksum(a[0, f] * x_vals[f] for f in features)
        model.addCons(expr + eps <= b[0] + M * (1 - z[i, 1]), name=f"route_left_{i}")
        model.addCons(expr >= b[0] - M * (1 - z[i, 2]), name=f"route_right_{i}")

    # Error minimization
    L = {}
    for i in range(len(data)):
        L[i] = model.addVar(vtype="C", name=f"L_{i}", lb=0)

    for i, row in enumerate(data):
        y = row[-1]
        for t in leaf_nodes:
            for k in classes:
                if k != y:
                    model.addCons(L[i] >= z[i, t] + c[t, k] - 1, name=f"err_{i}_{t}_{k}")

    model.setObjective(quicksum(L[i] for i in range(len(data))), "minimize")
    model.data = dict(a=a, b=b, c=c, z=z)

    return model


def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())


if __name__ == "__main__":
    main()
