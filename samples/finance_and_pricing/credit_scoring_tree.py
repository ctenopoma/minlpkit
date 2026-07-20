"""信用リスク評価の閾値分類 (Credit Scoring Threshold Optimization)

事業ストーリー
--------------
消費者金融の与信審査部門が、申込者を「承認/謝絶」に振り分けるスコアカットオフを
決める。カットオフを下げれば承認件数(=金利収入)は増えるが、デフォルト(貸倒れ)
リスクの高い申込者まで承認してしまう。年齢層(若年層/シニア層)でリスク特性が
異なるため、セグメントごとに別々のカットオフを最適化する。

各制約の業務的意味:
- **承認判定とスコアの整合性(big-M制約)**: 申込者を承認するなら、そのスコアは
  セグメントのカットオフ以上でなければならない(逆に、承認しないならこの制約を
  無効化する)。二値の承認フラグとカットオフ(連続変数)を同時最適化する点が
  素朴な固定閾値ルールとの違い。
- **セグメント別謝絶率の上限**: 公平貸付(fair lending)の観点から、
  各セグメントの謝絶率が一定を超えないようにする(規制・レピュテーションリスク対応)。
- **期待損益最大化**: 承認した申込者について、優良層からの期待金利収入と
  不良層への期待貸倒損失の差(データにより既知)を合計する。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

# 申込者データ: (セグメント, 信用スコア, 承認した場合の期待損益$)
APPLICANTS = [
    ("young", 620, 80), ("young", 580, -150), ("young", 700, 210),
    ("young", 540, -300), ("young", 660, 130),
    ("senior", 640, 60), ("senior", 590, -120), ("senior", 720, 260),
    ("senior", 560, -260), ("senior", 680, 150),
]
SEGMENTS = ["young", "senior"]
SCORE_MIN, SCORE_MAX = 300, 850
BIG_M = SCORE_MAX - SCORE_MIN
MAX_REJECT_RATE = 0.6   # セグメントごとの謝絶率上限


def build_model():
    model = Model("Credit_Scoring_Tree")

    cutoff = {seg: model.addVar(vtype="C", lb=SCORE_MIN, ub=SCORE_MAX, name=f"cutoff_{seg}")
              for seg in SEGMENTS}
    accept = {i: model.addVar(vtype="B", name=f"accept_{i}") for i in range(len(APPLICANTS))}

    for i, (seg, score, _) in enumerate(APPLICANTS):
        # accept[i]=1 ならスコア >= カットオフ
        model.addCons(score >= cutoff[seg] - BIG_M * (1 - accept[i]), f"accept_link_lo_{i}")
        # accept[i]=0 ならスコア < カットオフ(の緩和版: スコア <= カットオフ-1+BIG_M*accept)
        model.addCons(score <= cutoff[seg] - 1 + BIG_M * accept[i], f"accept_link_hi_{i}")

    for seg in SEGMENTS:
        idx = [i for i, (s, _, _) in enumerate(APPLICANTS) if s == seg]
        n_seg = len(idx)
        model.addCons(
            quicksum(1 - accept[i] for i in idx) <= MAX_REJECT_RATE * n_seg,
            f"reject_cap_{seg}")

    expected_profit = quicksum(APPLICANTS[i][2] * accept[i] for i in range(len(APPLICANTS)))
    model.setObjective(expected_profit, "maximize")
    model.data = {"cutoff": cutoff, "accept": accept}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Expected Profit:", m.getObjVal())
