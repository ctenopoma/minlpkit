"""広告予算メディアミックス配分 (Media Mix Advertising).

マーケティング部門のメディアプランナーが、四半期の広告予算を複数のメディア
(TV・Web・新聞・SNSなど)と複数のキャンペーン期間(週・月単位)に分けて配分し、
総露出(リーチ)を最大化する予算配分問題である。各メディアは出稿量を増やすほど
1単位あたりの効果が逓減する(飽和効果)ため露出関数は区分線形で近似し、
またメディアには最低出稿額(契約上の下限枠)と期間ごとの予算上限があるため、
単純な線形な比例配分では表現できない構造になる。さらに特定メディア(TVなど)への
出稿有無自体が固定費(制作費)を伴う意思決定であるため、出稿するかどうかの
オン/オフ(整数)も同時に決める。

scale ノブ:
    small   : メディア3 × 期2 (テスト用)
    default : メディア4 × 期3
    large   : メディア5 × 期4
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_media=3, n_period=2),
    "default": dict(n_media=4, n_period=3),
    "large":   dict(n_media=5, n_period=4),
}

N_SEG = 3            # 区分線形の飽和効果を近似するセグメント数
PERIOD_BUDGET = 10000.0


def _data(scale: str):
    cfg = SCALES[scale]
    nM, nP = cfg["n_media"], cfg["n_period"]
    rng = np.random.default_rng(20260724 + nM * 29 + nP * 3)

    # セグメントごとの限界露出効率(逓減: セグメントが進むほど効率が下がる)
    base_eff = rng.uniform(3.0, 9.0, nM)
    seg_width = PERIOD_BUDGET / (nM * N_SEG) * np.ones((nM, N_SEG)) * 1.5
    seg_eff = np.zeros((nM, N_SEG))
    for i in range(nM):
        for s in range(N_SEG):
            seg_eff[i, s] = base_eff[i] * (0.72 ** s)

    fixed_cost = rng.uniform(300.0, 900.0, nM)     # 出稿する場合の制作固定費
    min_spend = rng.uniform(200.0, 600.0, nM)       # 契約上の最低出稿額(出稿する場合)

    return dict(nM=nM, nP=nP, seg_width=seg_width, seg_eff=seg_eff,
                fixed_cost=fixed_cost, min_spend=min_spend)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nM, nP = d["nM"], d["nP"]
    seg_width, seg_eff = d["seg_width"], d["seg_eff"]
    fixed_cost, min_spend = d["fixed_cost"], d["min_spend"]

    model = Model("Media_Mix")
    M, PER, S = range(nM), range(nP), range(N_SEG)

    x = {(i, p, s): model.addVar(vtype="C", lb=0.0, ub=float(seg_width[i, s]),
                                  name=f"x_{i}_{p}_{s}") for i in M for p in PER for s in S}
    spend = {(i, p): model.addVar(vtype="C", lb=0.0, name=f"spend_{i}_{p}") for i in M for p in PER}
    use = {(i, p): model.addVar(vtype="B", name=f"use_{i}_{p}") for i in M for p in PER}

    for p in PER:
        model.addCons(
            quicksum(spend[i, p] + float(fixed_cost[i]) * use[i, p] for i in M) <= PERIOD_BUDGET,
            name=f"budget_{p}")
        for i in M:
            model.addCons(
                spend[i, p] == quicksum(x[i, p, s] for s in S), name=f"spend_def_{i}_{p}")
            # 出稿する場合のみ支出でき、最低出稿額(契約枠)を満たす必要がある
            total_seg_cap = float(seg_width[i].sum())
            model.addCons(spend[i, p] <= total_seg_cap * use[i, p], name=f"onoff_ub_{i}_{p}")
            model.addCons(spend[i, p] >= float(min_spend[i]) * use[i, p], name=f"onoff_lb_{i}_{p}")

    exposures = quicksum(
        float(seg_eff[i, s]) * x[i, p, s] for i in M for p in PER for s in S)
    fixed_total = quicksum(float(fixed_cost[i]) * use[i, p] for i in M for p in PER)
    model.setObjective(exposures - 0.0 * fixed_total, "maximize")
    model.data = {"x": x, "spend": spend, "use": use, "scale": scale, "dims": (nM, nP)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Exposures:", m.getObjVal())


if __name__ == "__main__":
    main()
