"""石油調達→プーリング→製品ブレンドの多期計画 (Multi-period Petroleum Pooling).

事業ストーリー
--------------
中堅の石油精製・調達会社の「調達計画部」が、数週間の計画期間について、
どの原料(スイート/サワー原油・各種留分)を、いつ、どれだけ買い付け、
どの中間タンク(プール)に入れ、そこからどの製品(プレミアム/レギュラー等)へ
ブレンドするかを決める意思決定である。

各制約の業務的意味:
- **調達契約 on/off(固定費 + 最小引取量)**: 供給元と期ごとに契約を結ぶと固定費が発生し、
  契約した期は最小引取量以上を買う義務がある(take-or-pay 的)。→ バイナリ z[i,t]。
- **タンク(プール)在庫の期跨ぎ**: 買った原料は一旦中間タンクに貯め、後の期に払い出せる。
  タンクは容量上限を持ち、在庫は次期へ持ち越される(=期分解を妨げる時間結合)。
- **プール品質 = 流入の流量加重平均(双線形=プーリング問題の核)**: タンクは良く撹拌された
  混合物で、その硫黄濃度は「硫黄質量在庫 ÷ 体積在庫」。払い出し時はこの濃度で硫黄が出ていく。
  濃度×流量・濃度×在庫の**双線形項**が本質的に現れる(well-mixed blend tank)。
- **製品の品質仕様(硫黄分の上限)**: 各製品は硫黄分の規格上限を持ち、タンクから受け取る
  ブレンドの加重平均濃度が規格を超えてはならない(環境規制・製品スペック)。
- **スポット市場バックストップ(高コスト)**: 自社ブレンドで需要を賄えない分は、規格適合の
  完成品をスポット市場から割高に購入して充足できる(常に実行可能性を担保する現実の逃げ道)。
  最適解では割高なスポットより自社プーリングが選ばれるが、これがあることで求解は常に可行解を持つ。

なぜ非凸が業務要件として自然に入るか:
タンクの「混ぜて貯めて後で使う」という現実の運用そのものが、濃度(連続)×流量(連続)の
双線形を生む。これはプーリング問題として古典的に強い非凸(NP困難)であり、近似ではなく
事業運用の物理そのものである。SCIP は空間分枝限定法で厳密求解する。

scale ノブ(硬さの源泉: 現実規模 + 物理結合 + 時間結合):
    small   : 原料3 × プール2 × 製品2 × 期3   (テスト・ハンズオン用。数分で最適)
    default : 原料7 × プール4 × 製品4 × 期8   (診断の題材。30秒でgap残存)
    large   : 原料8 × プール6 × 製品5 × 期10
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_feed=3, n_pool=2, n_prod=2, n_period=3),
    "default": dict(n_feed=8, n_pool=5, n_prod=4, n_period=8),
    "large":   dict(n_feed=10, n_pool=7, n_prod=6, n_period=12),
}


def _data(scale: str):
    cfg = SCALES[scale]
    nF, nL, nJ, nT = cfg["n_feed"], cfg["n_pool"], cfg["n_prod"], cfg["n_period"]
    rng = np.random.default_rng(20260720 + nF * 131 + nL * 17 + nJ * 7 + nT)

    # 原料の硫黄含有量 wt%(0.2=スイート 〜 3.0=サワー)
    sulfur = np.round(rng.uniform(0.2, 3.0, nF), 3)
    # 基準コスト: 低硫黄(スイート)ほど高い(現実の価格構造)。$/bbl
    base_cost = np.round(75.0 - 12.0 * sulfur + rng.uniform(-4, 4, nF), 2)
    base_cost = np.maximum(base_cost, 30.0)
    # 期別の市況変動(山谷)
    market = 1.0 + 0.18 * np.sin(np.linspace(0, 3.1, nT)) + rng.uniform(-0.05, 0.05, nT)
    cost = np.round(np.outer(base_cost, market), 2)               # cost[i,t]
    # 原料の期別供給可能量
    avail = np.round(rng.uniform(40, 90, (nF, nT)), 1)            # avail[i,t]
    # 契約固定費・最小引取量
    fix_cost = np.round(rng.uniform(80, 200, nF), 1)
    min_buy = np.round(rng.uniform(3, 9, nF), 1)

    # プール容量・在庫保管費
    pool_cap = np.round(rng.uniform(60, 120, nL), 1)
    hold = np.round(rng.uniform(0.5, 1.5, nL), 2)

    # 製品: 需要(山谷)・硫黄規格上限
    base_dem = rng.uniform(25, 55, nJ)
    season = 1.0 + 0.30 * np.sin(np.linspace(0.5, 3.5, nT))
    demand = np.round(np.outer(base_dem, season) + rng.uniform(-4, 4, (nJ, nT)), 1)
    demand = np.maximum(demand, 8.0)                              # demand[j,t]
    s_min, s_max = float(sulfur.min()), float(sulfur.max())
    # 規格は blendable だがタイト(最小硫黄寄り)。低硫黄=高コスト原料の精密ブレンドを強制し、
    # プール横断の配合最適化(=強い非凸)を要求する。
    spec = np.round(rng.uniform(s_min + 0.20, s_min + 0.45 * (s_max - s_min), nJ), 3)

    return dict(nF=nF, nL=nL, nJ=nJ, nT=nT, sulfur=sulfur, cost=cost,
                avail=avail, fix_cost=fix_cost, min_buy=min_buy,
                pool_cap=pool_cap, hold=hold, demand=demand, spec=spec,
                s_min=s_min, s_max=s_max)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nF, nL, nJ, nT = d["nF"], d["nL"], d["nJ"], d["nT"]
    sulfur, cost, avail = d["sulfur"], d["cost"], d["avail"]
    fix_cost, min_buy = d["fix_cost"], d["min_buy"]
    pool_cap, hold = d["pool_cap"], d["hold"]
    demand, spec = d["demand"], d["spec"]
    s_min, s_max = d["s_min"], d["s_max"]

    m = Model("Petroleum_Pooling_MultiPeriod")

    F = range(nF); L = range(nL); J = range(nJ); T = range(nT)

    # --- 変数 ---
    z = {(i, t): m.addVar(vtype="B", name=f"z_{i}_{t}") for i in F for t in T}
    x = {(i, l, t): m.addVar(vtype="C", lb=0.0, ub=float(avail[i, t]),
                             name=f"x_{i}_{l}_{t}")
         for i in F for l in L for t in T}
    y = {(l, j, t): m.addVar(vtype="C", lb=0.0, name=f"y_{l}_{j}_{t}")
         for l in L for j in J for t in T}
    inv = {(l, t): m.addVar(vtype="C", lb=0.0, ub=float(pool_cap[l]),
                            name=f"inv_{l}_{t}") for l in L for t in T}
    smass = {(l, t): m.addVar(vtype="C", lb=0.0,
                              ub=float(pool_cap[l]) * s_max,
                              name=f"smass_{l}_{t}") for l in L for t in T}
    conc = {(l, t): m.addVar(vtype="C", lb=s_min, ub=s_max, name=f"conc_{l}_{t}")
            for l in L for t in T}
    # スポット完成品(規格適合=硫黄0相当・高コスト): 実行可能性のバックストップ
    spot = {(j, t): m.addVar(vtype="C", lb=0.0, name=f"spot_{j}_{t}")
            for j in J for t in T}
    # スポット単価は自社ブレンドの最高原料コストより十分高く設定
    spot_cost = float(cost.max()) * 2.2

    # --- 制約 ---
    # 1. 調達契約: 契約した期のみ買え、最小引取量以上(take-or-pay)
    for i in F:
        for t in T:
            m.addCons(quicksum(x[i, l, t] for l in L) <= float(avail[i, t]) * z[i, t],
                      name=f"contract_ub_{i}_{t}")
            m.addCons(quicksum(x[i, l, t] for l in L) >= float(min_buy[i]) * z[i, t],
                      name=f"contract_lb_{i}_{t}")

    # 2. 体積在庫バランス(期跨ぎ): I_lt = I_{l,t-1} + 流入 - 流出
    for l in L:
        for t in T:
            prev = inv[l, t - 1] if t > 0 else 0.0
            m.addCons(
                inv[l, t] == prev
                + quicksum(x[i, l, t] for i in F)
                - quicksum(y[l, j, t] for j in J),
                name=f"vol_balance_{l}_{t}")

    # 3. 硫黄質量バランス(双線形: 払い出し濃度 × 流出量)
    for l in L:
        for t in T:
            prev = smass[l, t - 1] if t > 0 else 0.0
            out_vol = quicksum(y[l, j, t] for j in J)
            m.addCons(
                smass[l, t] == prev
                + quicksum(float(sulfur[i]) * x[i, l, t] for i in F)
                - conc[l, t] * out_vol,
                name=f"sulfur_balance_{l}_{t}")

    # 4. 濃度の定義(双線形): 硫黄質量在庫 = 濃度 × 体積在庫
    for l in L:
        for t in T:
            m.addCons(smass[l, t] == conc[l, t] * inv[l, t],
                      name=f"conc_def_{l}_{t}")

    # 5. 需要充足: 各製品の受取総量 >= 需要
    for j in J:
        for t in T:
            m.addCons(quicksum(y[l, j, t] for l in L) >= float(demand[j, t]),
                      name=f"demand_{j}_{t}")

    # 6. 製品品質規格(双線形): 加重平均硫黄濃度 <= 規格上限
    for j in J:
        for t in T:
            recv = quicksum(y[l, j, t] for l in L)
            sulf = quicksum(conc[l, t] * y[l, j, t] for l in L)
            m.addCons(sulf <= float(spec[j]) * recv, name=f"spec_{j}_{t}")

    # --- 目的関数: 調達コスト + 契約固定費 + 在庫保管費 の最小化 ---
    buy_cost = quicksum(float(cost[i, t]) * x[i, l, t]
                        for i in F for l in L for t in T)
    fixed = quicksum(float(fix_cost[i]) * z[i, t] for i in F for t in T)
    holding = quicksum(float(hold[l]) * inv[l, t] for l in L for t in T)
    m.setObjective(buy_cost + fixed + holding, "minimize")

    m.data = {"z": z, "x": x, "y": y, "inv": inv, "smass": smass, "conc": conc,
              "scale": scale, "dims": (nF, nL, nJ, nT)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
