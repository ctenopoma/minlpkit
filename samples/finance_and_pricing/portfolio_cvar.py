"""条件付き確実性価値 (CVaR) ポートフォリオ最適化 (Portfolio CVaR).

資産運用担当者が、複数の資産クラス(株式・債券・オルタナティブなど)への
配分比率を、複数のシナリオ(景気後退・平常・好況など、過去データから抽出した
シミュレーションシナリオ)にわたるテール損失(条件付きVaR、CVaR)を一定水準以下に
抑えながら期待リターンを最大化するように決める資産配分問題である。CVaRは
「最悪の一定割合のシナリオにおける平均損失」であり、Rockafellar-Uryasev の
線形計画定式化によって補助変数(VaR水準と各シナリオの超過損失)を導入することで
線形制約として扱える。単純な分散を使う平均分散モデルと異なり、テールリスクを
直接制約できるためリスク管理部門の要件に自然に合致する。

scale ノブ:
    small   : 資産3 × シナリオ8 (テスト用)
    default : 資産5 × シナリオ20
    large   : 資産7 × シナリオ40
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_asset=3, n_scen=8),
    "default": dict(n_asset=5, n_scen=20),
    "large":   dict(n_asset=7, n_scen=40),
}

ALPHA = 0.95          # CVaRの信頼水準(下位5%シナリオを問題視)
CVAR_LIMIT = 0.22      # 許容CVaR上限(ポートフォリオ損失率)


def _data(scale: str):
    cfg = SCALES[scale]
    nA, nS = cfg["n_asset"], cfg["n_scen"]
    rng = np.random.default_rng(20260724 + nA * 43 + nS * 3)

    mean_ret = rng.uniform(0.02, 0.10, nA)
    vol = rng.uniform(0.05, 0.30, nA)
    # 資産間の相関を粗く再現するため共通ファクター+固有ノイズでシナリオリターンを生成
    factor = rng.normal(0.0, 1.0, nS)
    scen_ret = np.zeros((nS, nA))
    for i in range(nA):
        idio = rng.normal(0.0, 1.0, nS)
        scen_ret[:, i] = mean_ret[i] + vol[i] * (0.6 * factor + 0.8 * idio)

    return dict(nA=nA, nS=nS, mean_ret=mean_ret, scen_ret=scen_ret)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nA, nS = d["nA"], d["nS"]
    mean_ret, scen_ret = d["mean_ret"], d["scen_ret"]

    model = Model("Portfolio_CVaR")
    A, S = range(nA), range(nS)

    w = {i: model.addVar(vtype="C", lb=0.0, ub=1.0, name=f"w_{i}") for i in A}
    var_level = model.addVar(vtype="C", lb=-1.0, name="var_level")  # VaR(閾値)
    excess = {s: model.addVar(vtype="C", lb=0.0, name=f"excess_{s}") for s in S}

    model.addCons(quicksum(w[i] for i in A) == 1.0, name="budget")

    for s in S:
        scen_loss = -quicksum(float(scen_ret[s, i]) * w[i] for i in A)
        # Rockafellar-Uryasev線形化: 超過損失 = max(0, シナリオ損失 - VaR)
        model.addCons(excess[s] >= scen_loss - var_level, name=f"cvar_excess_{s}")

    cvar = var_level + (1.0 / ((1.0 - ALPHA) * nS)) * quicksum(excess[s] for s in S)
    model.addCons(cvar <= CVAR_LIMIT, name="cvar_limit")

    model.setObjective(quicksum(float(mean_ret[i]) * w[i] for i in A), "maximize")
    model.data = {"w": w, "var_level": var_level, "excess": excess,
                  "scale": scale, "dims": (nA, nS)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Expected Return:", m.getObjVal())


if __name__ == "__main__":
    main()
