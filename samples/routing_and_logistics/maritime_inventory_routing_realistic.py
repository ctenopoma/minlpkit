"""複数船舶の配船スケジューリング+港湾在庫統合計画 (Realistic Maritime Inventory Routing).

事業ストーリー
--------------
海運会社の配船計画者が、異なる積載容量を持つ複数のタンカー(船隊)について、
「どの船をいつどの港に配船するか(整数の配船スケジュール)」と「各港でどれだけ
荷役するか(積載量、在庫制約付き)」を**同時に**決める意思決定である。
既存の `maritime_inventory_routing.py`(Phase 16 精緻化版)は「期あたりの
隻数」という集計的な決定だったのに対し、本モデルは個々の船舶を区別し、
1隻が1つの寄港を終えてから次の寄港まで一定期間(往復の航海時間)は
使えないという**現実の航海サイクル(時間結合)**を明示的に扱う点で異なる。

各制約の業務的意味:
- **船舶ごとの配船決定(整数)**: 各船舶 v は各期 t に高々1つの港を訪問できる
  (`assign[v,p,t]` バイナリ、`sum_p assign[v,p,t] <= 1`)。同時に複数港へは
  行けないという物理的制約。
- **船舶容量×積載量の結合**: 積載量は配船した船の容量を超えられない
  (`qty[v,p,t] <= cap[v] * assign[v,p,t]`)。船隊は異容量(小型/中型/大型)
  混成であり、大型船を大口港に割り当てるほど効率的だが航海サイクルが長い
  というトレードオフを持つ。
- **航海サイクル(時間結合、真の結合の核)**: 船が期 t に港へ着岸すると、
  積み下ろし・往路復路にかかる `transit[v]` 期の間はその船を別の配船に
  使えない(`sum_{t'=t-transit[v]+1}^{t} sum_p assign[v,p,t'] <= 1`)。
  これにより「今この船をこの港に使う」判断が将来何期かの船の可用性を
  拘束し、期を独立に最適化できない(=クルーズ/往復輸送そのものが生む
  スケジューリングの結合)。
- **複数港が同じ船隊を取り合う構造(統合意思決定)**: 船隊は特定の港専用
  ではなく全社共有であり、`assign` の1隻1期あたり高々1港制約と航海
  サイクル制約を通じて、ある港への配船が他港の配船機会を奪う。
- **港湾在庫バランス(時間結合)**: 各港は消費(出荷)ペースに応じて在庫が
  自然に減っていき、下限を割る前に補充が必要。在庫上限(タンク容量)も
  超えられない。
- **緊急スポット輸送バックストップ(高コスト)**: 自社船隊で賄えない港の
  補充は、割高なスポット用船(chartered vessel)で埋められる。常時実行
  可能性を担保する現実の逃げ道。

なぜ結合が業務要件として自然に入るか:
タンカーは瞬間移動できず、積み下ろしと航海には物理的な時間がかかる
(往復航海サイクル)。この現実の制約が「今の配船判断が将来の配船能力を
拘束する」という時間結合を生み、かつ船隊が複数港で共有される限られた
資産である以上、ある港への手厚い配船は他港の在庫リスクを高める
(統合意思決定)。これは近似ではなく実際の海運オペレーションの構造である。

scale ノブ(硬さの源泉: 現実規模 + 統合意思決定(共有船隊) + 時間結合(航海サイクル)):
    small   : 船3(容量混成) × 港3 × 期6    (テスト・ハンズオン用。数分で最適)
    default : 船5(容量混成) × 港6 × 期10   (診断の題材)
    large   : 船6 × 港8 × 期12
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_ship=3, n_port=3, n_t=6),
    "default": dict(n_ship=5, n_port=6, n_t=10),
    "large":   dict(n_ship=6, n_port=8, n_t=12),
}


def _data(scale: str):
    cfg = SCALES[scale]
    nV, nP, nT = cfg["n_ship"], cfg["n_port"], cfg["n_t"]
    rng = np.random.default_rng(20260720 + nV * 71 + nP * 19 + nT * 5)

    # 船隊: 容量混成(小型/中型/大型が周期的に混ざる)・航海サイクル日数(期)・配船コスト
    cap_choices = np.array([28.0, 40.0, 55.0])
    ship_cap = cap_choices[np.arange(nV) % 3]
    ship_cap = ship_cap + rng.uniform(-3.0, 3.0, nV)
    transit = 2 + (np.arange(nV) % 3)                        # 2〜4期の航海サイクル
    ship_cost = np.round(15.0 + 0.35 * ship_cap + rng.uniform(-3, 3, nV), 1)

    # 港: 消費ペース(山谷)・在庫上限下限・保管費
    # 船隊の総輸送能力(容量×航海頻度)を港の総消費量とほぼ拮抗させ、常時
    # タイトな配船の取り合い(bin-packing的な組合せ判断)を生む(硬さの調整弁)。
    fleet_throughput_per_period = float(np.sum(ship_cap / transit))
    base_cons = rng.uniform(0.85, 1.0, nP)
    base_cons = base_cons / base_cons.sum() * fleet_throughput_per_period * 0.94
    season = 1.0 + 0.25 * np.sin(np.linspace(0.4, 3.4, nT))
    consumption = np.round(np.outer(base_cons, season) + rng.uniform(-0.5, 0.5, (nP, nT)), 2)
    consumption = np.maximum(consumption, 1.0)
    inv_min = np.round(rng.uniform(10.0, 18.0, nP), 1)
    inv_max = np.round(inv_min + rng.uniform(20.0, 35.0, nP), 1)
    inv0 = np.round(inv_min + 0.55 * (inv_max - inv_min), 1)
    hold_cost = np.round(rng.uniform(0.4, 0.9, nP), 2)

    # 港-船の相性コスト(距離依存の単価、荷役単価)
    unit_cost = np.round(rng.uniform(0.8, 2.0, (nV, nP)), 2)

    return dict(nV=nV, nP=nP, nT=nT, ship_cap=ship_cap, transit=transit,
                ship_cost=ship_cost, consumption=consumption, inv_min=inv_min,
                inv_max=inv_max, inv0=inv0, hold_cost=hold_cost, unit_cost=unit_cost)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nV, nP, nT = d["nV"], d["nP"], d["nT"]
    ship_cap, transit, ship_cost = d["ship_cap"], d["transit"], d["ship_cost"]
    consumption, inv_min, inv_max, inv0 = d["consumption"], d["inv_min"], d["inv_max"], d["inv0"]
    hold_cost, unit_cost = d["hold_cost"], d["unit_cost"]

    m = Model("Maritime_Inventory_Routing_Realistic")
    V, P, T = range(nV), range(nP), range(nT)

    # --- 変数 ---
    assign = {(v, p, t): m.addVar(vtype="B", name=f"assign_{v}_{p}_{t}")
              for v in V for p in P for t in T}
    qty = {(v, p, t): m.addVar(vtype="C", lb=0.0, name=f"qty_{v}_{p}_{t}")
           for v in V for p in P for t in T}
    inv = {(p, t): m.addVar(vtype="C", lb=0.0, ub=float(inv_max[p]), name=f"inv_{p}_{t}")
           for p in P for t in T}
    # 緊急スポット輸送(高コスト): 常時実行可能性を担保
    spot = {(p, t): m.addVar(vtype="C", lb=0.0, name=f"spot_{p}_{t}") for p in P for t in T}
    spot_cost = float(unit_cost.max()) * 8.0

    # --- 制約 ---
    # 1. 各船は各期に高々1港のみ訪問
    for v in V:
        for t in T:
            m.addCons(quicksum(assign[v, p, t] for p in P) <= 1, name=f"one_port_{v}_{t}")

    # 2. 船舶容量×積載量の結合: 積載は配船した船の容量まで
    for v in V:
        for p in P:
            for t in T:
                m.addCons(qty[v, p, t] <= float(ship_cap[v]) * assign[v, p, t],
                          name=f"cap_{v}_{p}_{t}")

    # 3. 航海サイクル(時間結合): 着岸後 transit[v] 期の間は再配船不可
    for v in V:
        tr = int(transit[v])
        for t in T:
            window = range(max(0, t - tr + 1), t + 1)
            m.addCons(
                quicksum(assign[v, p, tt] for p in P for tt in window) <= 1,
                name=f"cycle_{v}_{t}")

    # 4. 港湾在庫バランス(時間結合)+ 下限維持(積み下ろし+スポットで補充)
    for p in P:
        for t in T:
            prev = inv0[p] if t == 0 else inv[p, t - 1]
            inflow = quicksum(qty[v, p, t] for v in V) + spot[p, t]
            m.addCons(
                inv[p, t] == prev - float(consumption[p, t]) + inflow,
                name=f"balance_{p}_{t}")
            m.addCons(inv[p, t] >= float(inv_min[p]), name=f"inv_min_{p}_{t}")

    # --- 目的関数: 配船固定費+荷役可変費+在庫保管費+スポットバックストップ ---
    dispatch = quicksum(float(ship_cost[v]) * assign[v, p, t]
                        for v in V for p in P for t in T)
    handling = quicksum(float(unit_cost[v, p]) * qty[v, p, t]
                        for v in V for p in P for t in T)
    holding = quicksum(float(hold_cost[p]) * inv[p, t] for p in P for t in T)
    spot_pen = quicksum(spot_cost * spot[p, t] for p in P for t in T)
    m.setObjective(dispatch + handling + holding + spot_pen, "minimize")

    m.data = {"assign": assign, "qty": qty, "inv": inv, "spot": spot,
              "scale": scale, "dims": (nV, nP, nT)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
