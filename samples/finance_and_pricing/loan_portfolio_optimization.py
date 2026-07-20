"""ローン与信ポートフォリオ利回り最大化 (Loan Portfolio Optimization).

銀行の与信ポートフォリオ管理者が、複数の融資商品(住宅・消費者・中小企業向けなど)
に対して四半期ごとの新規貸出枠をどう配分するかを、期待利回りが最大になるように
決める与信配分問題である。各商品にはデフォルト確率に応じたリスクウェイトがあり、
規制上・社内方針上、ポートフォリオ全体の加重平均デフォルト率や特定セグメント
(高リスク商品群)への集中度に上限が課される。さらに各商品には「新規開拓できる
案件数には限りがある」という現実的な貸出枠上限があり、期をまたいで総貸出残高が
積み上がる(前期末残高+今期新規実行)ため、単純な一括配分ではなく複数期にわたる
資本配分計画になる。

scale ノブ:
    small   : 商品3 × 四半期2 (テスト用)
    default : 商品5 × 四半期4
    large   : 商品7 × 四半期6
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_prod=3, n_qtr=2),
    "default": dict(n_prod=5, n_qtr=4),
    "large":   dict(n_prod=7, n_qtr=6),
}

TOTAL_QUARTERLY_BUDGET = 1000.0
RISK_LIMIT = 0.032          # ポートフォリオ加重平均デフォルト率の上限
HIGH_RISK_SHARE_LIMIT = 0.35  # 高リスク商品群(デフォルト率上位)への配分比率上限


def _data(scale: str):
    cfg = SCALES[scale]
    nP, nQ = cfg["n_prod"], cfg["n_qtr"]
    rng = np.random.default_rng(20260724 + nP * 19 + nQ * 5)

    default_prob = np.sort(rng.uniform(0.005, 0.06, nP))
    yield_rate = 0.03 + 1.1 * default_prob + rng.uniform(-0.003, 0.003, nP)
    # 商品ごとの新規実行の四半期上限(開拓できる案件数の制約)
    origination_cap = rng.uniform(150.0, 350.0, nP)
    high_risk = default_prob >= np.median(default_prob)

    return dict(nP=nP, nQ=nQ, default_prob=default_prob, yield_rate=yield_rate,
                origination_cap=origination_cap, high_risk=high_risk)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nP, nQ = d["nP"], d["nQ"]
    default_prob, yield_rate = d["default_prob"], d["yield_rate"]
    origination_cap, high_risk = d["origination_cap"], d["high_risk"]

    model = Model("Loan_Portfolio")
    P, Q = range(nP), range(nQ)

    # 新規実行額(商品×四半期)
    orig = {(i, q): model.addVar(vtype="C", lb=0.0, ub=float(origination_cap[i]),
                                  name=f"orig_{i}_{q}") for i in P for q in Q}
    # 残高(前期残高+当期新規実行、簡易的に償還は無視した積み上げ残高)
    bal = {(i, q): model.addVar(vtype="C", lb=0.0, name=f"bal_{i}_{q}") for i in P for q in Q}

    for q in Q:
        model.addCons(quicksum(orig[i, q] for i in P) <= TOTAL_QUARTERLY_BUDGET,
                      name=f"budget_{q}")
        for i in P:
            if q == 0:
                model.addCons(bal[i, q] == orig[i, q], name=f"bal_init_{i}")
            else:
                model.addCons(bal[i, q] == bal[i, q - 1] + orig[i, q], name=f"bal_roll_{i}_{q}")

        total_bal_q = quicksum(bal[i, q] for i in P)
        # ポートフォリオ加重平均デフォルト率の上限(規制・社内リスク方針)
        model.addCons(
            quicksum(float(default_prob[i]) * bal[i, q] for i in P) <= RISK_LIMIT * total_bal_q,
            name=f"risk_limit_{q}")
        # 高リスク商品群への集中度上限
        model.addCons(
            quicksum(bal[i, q] for i in P if high_risk[i]) <= HIGH_RISK_SHARE_LIMIT * total_bal_q,
            name=f"concentration_{q}")

    model.setObjective(
        quicksum(float(yield_rate[i]) * bal[i, q] for i in P for q in Q), "maximize")
    model.data = {"orig": orig, "bal": bal, "scale": scale, "dims": (nP, nQ)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Yield:", m.getObjVal())


if __name__ == "__main__":
    main()
