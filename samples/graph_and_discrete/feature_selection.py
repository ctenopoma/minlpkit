"""特徴量選択によるスパース回帰 (MIP) — Feature Selection for Regression

事業ストーリー
--------------
臨床データ分析チームのデータサイエンティストが、健診受診者の検査値(血圧・BMI・
血糖値など10項目)から将来の健康リスクスコアを予測する回帰モデルを構築する。
検査項目が多いほど過学習や説明性の低下を招くため、採用する検査項目の上限を
4つまでに絞り込みつつ、予測誤差(絶対誤差の総和)を最小化する変数選択を行う
(いわゆる Best Subset Selection、元の学術名: Feature Selection for Regression)。

各制約の業務的意味:
- **bigM(beta<=M*z, beta>=-M*z)**: 回帰係数betaが非ゼロの値を取れるのは、
  対応する検査項目が選択された(z=1)ときだけ、という「選択されなければ
  モデルに使わない」を表す論理制約。
- **sparsity(sum z <= k_max)**: 臨床的に説明可能なモデルにするための
  検査項目数の上限(採用項目が多すぎると医師への説明が難しくなる)。
- **error(絶対誤差)**: 実測の健康リスクスコアと予測値の差を線形計画で
  扱うための上下からの絶対値評価。

参考文献: Bertsimas, D., King, A., & Mazumder, R. (2016). Best subset selection
via a modern optimization lens. The Annals of Statistics.
"""
from __future__ import annotations

import random

from pyscipopt import Model, quicksum

FEATURE_NAMES = [
    "収縮期血圧", "拡張期血圧", "BMI", "空腹時血糖", "HbA1c",
    "LDLコレステロール", "HDLコレステロール", "中性脂肪", "年齢", "喫煙歴スコア",
]


def make_instance(n_samples: int = 20, seed: int = 7):
    """検査値10項目から健康リスクスコアを生成する疑似健診データ(真の係数はスパース)。"""
    rng = random.Random(seed)
    n_features = len(FEATURE_NAMES)
    # 実際に効いているのはBMI・HbA1c・年齢の3項目のみ(スパースな真の関係を模擬)
    true_beta = [0.0] * n_features
    true_beta[2] = 0.9   # BMI
    true_beta[4] = 1.4   # HbA1c
    true_beta[8] = 0.6   # 年齢

    X = []
    y = []
    for _ in range(n_samples):
        row = [rng.uniform(0.0, 1.0) for _ in range(n_features)]
        score = sum(b * v for b, v in zip(true_beta, row)) + rng.uniform(-0.1, 0.1)
        X.append(row)
        y.append(score)
    return X, y


def build_model(infeasible=False):
    model = Model("FeatureSelection")

    X, y = make_instance()
    n_samples = len(X)
    n_features = len(X[0])
    k_max = 4  # 説明可能性のため、採用する検査項目は最大4つまで

    if infeasible:
        k_max = -1

    M = 10.0

    beta = {}
    z = {}
    error = {}

    for j in range(n_features):
        beta[j] = model.addVar(vtype="C", name=f"beta_{j}", lb=-M, ub=M)
        z[j] = model.addVar(vtype="B", name=f"z_{j}")

    for i in range(n_samples):
        # absolute error formulation for simplicity
        error[i] = model.addVar(vtype="C", name=f"error_{i}", lb=0)

    # Big-M constraints
    for j in range(n_features):
        model.addCons(beta[j] <= M * z[j], name=f"bigM_up_{j}")
        model.addCons(beta[j] >= -M * z[j], name=f"bigM_low_{j}")

    model.addCons(quicksum(z[j] for j in range(n_features)) <= k_max, name="sparsity")

    # Error constraints
    for i in range(n_samples):
        pred = quicksum(X[i][j] * beta[j] for j in range(n_features))
        model.addCons(error[i] >= y[i] - pred, name=f"err_up_{i}")
        model.addCons(error[i] >= pred - y[i], name=f"err_low_{i}")

    model.setObjective(quicksum(error[i] for i in range(n_samples)), "minimize")
    model.data = dict(beta=beta, z=z, feature_names=FEATURE_NAMES)

    return model


def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())


if __name__ == "__main__":
    main()
