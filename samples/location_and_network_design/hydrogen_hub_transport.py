"""水素サプライチェーン: ハブ配置 + 多期輸送計画 (Hydrogen Hub Location & Transport).

事業ストーリー
--------------
水素サプライチェーンを構築するエネルギー事業者の「計画担当者」が、候補地の中から
「どこに生産・貯蔵ハブを開設し、どれだけの生産・貯蔵容量を持たせるか」(整数の
開設可否 + 連続の容量)を決め、開設したハブから複数の需要地(水素ステーション等)へ
「複数期にわたってどれだけ輸送するか」(連続)を同時に決める投資・運用意思決定である。

各制約の業務的意味:
- **ハブ開設(整数)+ 生産・貯蔵容量(連続、big-M結合)**: ハブを開設しなければ
  生産・貯蔵容量はゼロでなければならない(固定費を払わない限り設備を持てない)。
  開設可否という整数決定が容量という連続変数の実行可能領域を直接規定する。
- **生産量 ≤ 生産容量**: 各期の生産量は投資した生産容量を超えられない。
- **貯蔵ダイナミクス(時間結合)**: 各期の在庫量は前期在庫+生産-出荷で決まり、
  貯蔵容量を超えられない。在庫を使って「今作るか、貯めて後で出荷するか」を
  期をまたいで最適化する必要がある。
- **輸送(連続、ハブ→需要地)**: 開設したハブから各需要地への輸送量・距離に応じた
  輸送費がかかる。輸送量に上限(トラック便数の実務的上限)がある。
- **需要充足 + 外部調達バックストップ**: 各需要地・各期の需要は、ハブからの輸送
  合計で賄うか、賄いきれない場合は高コストの外部調達(スポットローリー等)で
  補う(常時実行可能性の担保)。
- **構造上のベンダーズ分解適性**: 開設可否・容量(整数+連続の「複雑化変数」)を
  固定すれば、残る生産・貯蔵・輸送・外部調達の決定は各期をまたぐ在庫連続変数のみの
  **純粋な線形計画(LP)**になる。すなわち「配置=主問題(整数)」「輸送+在庫運用=
  サブ問題(LP)」という古典的な設備配置×輸送のベンダーズ分解構造を保つよう設計して
  ある(実際にベンダーズ分解を適用する必要はないが、構造としてその適性を持つ)。

なぜ結合が業務要件として自然に入るか:
水素ハブの開設・容量投資は一度決めれば数年単位で固定されるのに対し、輸送・在庫運用は
毎期の需要変動に応じて機動的に決める。開設可否が容量の存在自体を左右し(disjunctive/
big-M結合)、容量が生産・貯蔵という運用上限を規定するため、単独では易しい「配置問題」
と「輸送問題」がハブ容量という共有資源を通じて不可分に結合する — まさに古典的な
施設配置(facility location)と輸送計画の統合が本質的にNP困難である理由そのもの。

scale ノブ(硬さの源泉: 統合意思決定(ハブ開設・容量×輸送・在庫の同時決定) + 時間結合
(貯蔵ダイナミクス) + 現実規模(候補ハブ数×需要地数×期数)):
    small   : 候補ハブ4 × 需要地5 × 期6    (テスト・ハンズオン用。数分で最適)
    default : 候補ハブ7 × 需要地10 × 期10   (診断の題材。30秒でgap残存)
    large   : 候補ハブ12 × 需要地18 × 期16
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_hub=4,  n_dem=5,  n_period=6),
    "default": dict(n_hub=7,  n_dem=10, n_period=10),
    "large":   dict(n_hub=12, n_dem=18, n_period=16),
}

FIXED_COST_BASE = 180000.0      # ハブ開設固定費のベース[$]
COST_PROD_CAP = 850.0           # 生産容量投資費[$/(kg/期)]
COST_STOR_CAP = 220.0           # 貯蔵容量投資費[$/kg]
COST_PRODUCTION = 3.2           # 生産変動費[$/kg]
COST_TRANSPORT_PER_KM = 0.018   # 輸送費[$/(kg・km)]
COST_EXTERNAL = 14.0            # 外部調達バックストップ単価[$/kg](生産の数倍で高コスト)
TRUCK_CAP_PER_LINK = 900.0      # ハブ→需要地1本あたりの実務的輸送上限[kg/期]


def _data(scale: str):
    cfg = SCALES[scale]
    nH, nD, nT = cfg["n_hub"], cfg["n_dem"], cfg["n_period"]
    rng = np.random.default_rng(20260725 + nH * 61 + nD * 17 + nT * 3)

    # 候補ハブ・需要地の座標(輸送距離算出用)
    hub_xy = rng.uniform(0, 100, (nH, 2))
    dem_xy = rng.uniform(0, 100, (nD, 2))
    dist = np.sqrt(((hub_xy[:, None, :] - dem_xy[None, :, :]) ** 2).sum(axis=2))

    fixed_cost = np.round(FIXED_COST_BASE * rng.uniform(0.7, 1.4, nH), 0)

    # 需要: 期を通じて緩やかに増加するトレンド + 需要地ごとの水準差 + 季節ノイズ
    dem_level = rng.uniform(60.0, 160.0, nD)
    tt = np.arange(nT)
    trend = 1.0 + 0.35 * (tt / max(nT - 1, 1))
    demand = np.zeros((nD, nT))
    for j in range(nD):
        noise = 1.0 + rng.uniform(-0.06, 0.06, nT)
        demand[j] = dem_level[j] * trend * noise

    # 生産・貯蔵容量の実務的上限(容量投資の意思決定範囲)
    prod_cap_ub = float(demand.sum(axis=0).max()) * 0.55
    stor_cap_ub = float(demand.sum(axis=0).max()) * 1.2

    return dict(nH=nH, nD=nD, nT=nT, dist=dist, fixed_cost=fixed_cost,
                demand=demand, prod_cap_ub=prod_cap_ub, stor_cap_ub=stor_cap_ub)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nH, nD, nT = d["nH"], d["nD"], d["nT"]
    dist, fixed_cost, demand = d["dist"], d["fixed_cost"], d["demand"]
    prod_cap_ub, stor_cap_ub = d["prod_cap_ub"], d["stor_cap_ub"]

    m = Model("Hydrogen_Hub_Transport")
    H, Dm, T = range(nH), range(nD), range(nT)

    # --- 主問題側(複雑化変数): 開設・容量 ---
    open_hub = {h: m.addVar(vtype="B", name=f"open_{h}") for h in H}
    cap_prod = {h: m.addVar(vtype="C", lb=0.0, ub=prod_cap_ub, name=f"cap_prod_{h}") for h in H}
    cap_stor = {h: m.addVar(vtype="C", lb=0.0, ub=stor_cap_ub, name=f"cap_stor_{h}") for h in H}

    # --- サブ問題側(固定すればLP): 生産・在庫・輸送・外部調達 ---
    prod, stor, ship, ext = {}, {}, {}, {}
    for h in H:
        for t in T:
            prod[h, t] = m.addVar(vtype="C", lb=0.0, name=f"prod_{h}_{t}")
            for j in Dm:
                ship[h, j, t] = m.addVar(vtype="C", lb=0.0, ub=TRUCK_CAP_PER_LINK,
                                         name=f"ship_{h}_{j}_{t}")
        for t in range(nT + 1):
            stor[h, t] = m.addVar(vtype="C", lb=0.0, name=f"stor_{h}_{t}")
    for j in Dm:
        for t in T:
            ext[j, t] = m.addVar(vtype="C", lb=0.0, name=f"ext_{j}_{t}")

    for h in H:
        # 開設可否が容量の存在を規定(disjunctive/big-M結合)
        m.addCons(cap_prod[h] <= prod_cap_ub * open_hub[h], name=f"prod_cap_link_{h}")
        m.addCons(cap_stor[h] <= stor_cap_ub * open_hub[h], name=f"stor_cap_link_{h}")
        m.addCons(stor[h, 0] == 0.0, name=f"stor_init_{h}")
        for t in T:
            m.addCons(prod[h, t] <= cap_prod[h], name=f"prod_ub_{h}_{t}")
            m.addCons(stor[h, t] <= cap_stor[h], name=f"stor_ub_{h}_{t}")
            shipped_out = quicksum(ship[h, j, t] for j in Dm)
            # 貯蔵ダイナミクス(時間結合): 在庫 = 前期在庫 + 生産 - 出荷
            m.addCons(stor[h, t + 1] == stor[h, t] + prod[h, t] - shipped_out,
                      name=f"stor_balance_{h}_{t}")

    for j in Dm:
        for t in T:
            m.addCons(
                quicksum(ship[h, j, t] for h in H) + ext[j, t] == float(demand[j, t]),
                name=f"demand_{j}_{t}")

    fixed = quicksum(float(fixed_cost[h]) * open_hub[h] for h in H)
    invest = quicksum(COST_PROD_CAP * cap_prod[h] + COST_STOR_CAP * cap_stor[h] for h in H)
    production = quicksum(COST_PRODUCTION * prod[h, t] for h in H for t in T)
    transport = quicksum(COST_TRANSPORT_PER_KM * float(dist[h, j]) * ship[h, j, t]
                         for h in H for j in Dm for t in T)
    external = quicksum(COST_EXTERNAL * ext[j, t] for j in Dm for t in T)
    m.setObjective(fixed + invest + production + transport + external, "minimize")

    m.data = dict(open_hub=open_hub, cap_prod=cap_prod, cap_stor=cap_stor, ship=ship,
                  scale=scale, dims=(nH, nD, nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
