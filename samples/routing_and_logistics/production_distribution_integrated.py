"""生産-配送統合計画 (Integrated Production-Distribution / Lot-sizing + VRP-lite).

事業ストーリー
--------------
複数工場を持つメーカーの「生産・物流統合計画者」が、各週(期)について
(a) どの工場でいつ段取り(setup)して何を作るか(ロットサイジング)と
(b) 作った製品をどの配送センター(DC)へ何台のトラックで運ぶか(車両割当)を
**同時に**決める意思決定である。単独なら在庫管理を伴う簡単な生産計画・簡単な
輸送計画に分かれるが、この2つは以下の理由で不可分に結合している。

各制約の業務的意味:
- **段取り on/off + 生産能力(固定費+可変費)**: 工場は段取りした期のみ生産でき、
  段取りには固定費(ライン切替・清掃)がかかる。→ バイナリ `setup[f,t]`。
  生産量は段取りしない限りゼロ(big-M)。
- **工場在庫の期跨ぎ(時間結合)**: 作った分はすぐ全部出荷する必要はなく、
  工場倉庫に一旦貯めて後の期に出荷できる。在庫は容量上限を持つ。
- **生産しないと配送できない結合**: DCへの出荷量は工場の在庫バランス式
  (在庫 = 前期在庫 + 生産 - 出荷)から導かれるため、生産(段取り+ロット量)を
  決めずに出荷計画だけを単独最適化することはできない。
- **トラック割当(VRP的な容量制約)**: 工場→DC間の出荷はトラック単位で運ばれ、
  各トラックには積載上限がある。出荷量に対して必要なトラック数(整数)を
  往復あたりの発送固定費とともに決める。
- **複数工場が共有するトラック車隊(統合意思決定の核)**: トラックは特定の工場に
  紐付いた専用車両ではなく、期ごとに全社で共有するプールから配車される
  (`sum_{f,d} n_veh[f,d,t] <= fleet_size[t]`)。ある工場が多く使えば他工場は
  使える台数が減るため、生産計画(いつ・どの工場で作るか)と配車計画
  (どの工場発の便を優先するか)が拠点をまたいで結合する。単独工場・単独DCの
  問題に分解できない構造。
- **サードパーティ便バックストップ(高コスト)**: 自社便で賄えない需要は割高な
  外部委託配送(スポット便)で埋められる。常時実行可能性を担保する現実の逃げ道。
- **ドライバー労務時間(台数枠とは独立次元の共有資源)**: 遠距離便ほど拘束時間が
  長く、トラック台数の上限とは別に全社のドライバー労務時間にも上限がある。
  2つの独立なタイトな共有制約(台数・労務時間)が同時に効くため、単純に
  「近いDCから優先して台数を割り当てる」貪欲な発想では最適にならない
  多次元ナップサック的な組合せ判断を強制する。

なぜ結合が業務要件として自然に入るか:
現実の複数拠点メーカーでは、トラック(あるいは契約運送会社の枠)もドライバーの
労務時間も工場ごとに専有されるのではなく全社の物流部門が一元管理する共有資産
である。ある工場が段取りを後ろ倒しにして出荷が遅れれば、その分の車両枠・
労務時間枠が他工場の出荷に回る、という相互作用は分離不可能な結合であり、
これが本モデルの硬さの源泉になる(純粋な工場×DCの分離可能な積ではなく、
`fleet_size[t]`・`labor_cap[t]` という2つの共有リソースの奪い合いによって
拠点間が結合する)。

scale ノブ(硬さの源泉: 現実規模 + 統合意思決定 + 時間結合 + 多次元共有リソース):
    small   : 工場2 × DC3 × 期3     (テスト・ハンズオン用。1秒未満で最適)
    default : 工場9 × DC16 × 期14   (診断の題材。大規模な多次元ナップサック構造で
              30秒ではLPすら解ききれずgapが大きく残る)
    large   : 工場10 × DC18 × 期16
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_fac=2, n_dc=3, n_t=3),
    "default": dict(n_fac=9, n_dc=16, n_t=14),
    "large":   dict(n_fac=10, n_dc=18, n_t=16),
}

VEH_CAP = 45.0  # 1台のトラック積載上限 [トン](DC需要の1-2台分程度=丸め判断が効く粒度)


def _data(scale: str):
    cfg = SCALES[scale]
    nF, nD, nT = cfg["n_fac"], cfg["n_dc"], cfg["n_t"]
    rng = np.random.default_rng(20260720 + nF * 97 + nD * 13 + nT * 5)

    # 生産: 可変費・段取り固定費・生産能力・在庫容量・保管費
    prod_cost = np.round(rng.uniform(8.0, 16.0, nF), 2)
    setup_cost = np.round(rng.uniform(300.0, 700.0, nF), 1)
    inv_cap = np.round(rng.uniform(50.0, 90.0, nF), 1)
    hold_cost = np.round(rng.uniform(0.4, 1.0, nF), 2)

    # 輸送: 工場-DC間の距離依存コスト・トラック発送固定費
    lane_dist = np.round(rng.uniform(50.0, 400.0, (nF, nD)), 1)
    ship_cost = np.round(0.05 * lane_dist + rng.uniform(-1.0, 1.0, (nF, nD)), 2)
    ship_cost = np.maximum(ship_cost, 1.0)
    veh_dispatch_cost = np.round(0.30 * lane_dist + rng.uniform(-5, 5, (nF, nD)), 1)
    veh_dispatch_cost = np.maximum(veh_dispatch_cost, 10.0)
    # ドライバー労務時間(距離に比例、発送コストとは独立な比率): 車両台数上限とは
    # 別次元の共有資源(同じ便でも遠距離便ほど拘束時間が長い)。トラック台数枠と
    # 労務時間枠という2つの独立なタイトな共有制約が同時に効くことで、
    # 単純な貪欲な台数割当では最適にならない多次元ナップサック的な硬さを作る。
    drive_hours = np.round(1.0 + 0.018 * lane_dist + rng.uniform(-0.3, 0.3, (nF, nD)), 2)
    drive_hours = np.maximum(drive_hours, 0.5)

    # 需要(山谷)
    base_dem = rng.uniform(15.0, 35.0, nD)
    season = 1.0 + 0.30 * np.sin(np.linspace(0.3, 3.2, nT))
    demand = np.round(np.outer(base_dem, season) + rng.uniform(-3, 3, (nD, nT)), 1)
    demand = np.maximum(demand, 5.0)
    total_dem_per_t = demand.sum(axis=0)

    # 生産能力: 全工場合計でも期平均需要を若干上回る程度にタイト化。
    # 段取りを打つ期を分散させないと需要に追いつかず、在庫の先行生産(時間結合)と
    # 段取りタイミングのトレードオフ(古典的ロットサイジングの硬さ)を強制する。
    avg_dem = float(total_dem_per_t.mean())
    prod_share = rng.dirichlet(np.full(nF, 3.0))
    prod_cap = np.round(prod_share * avg_dem * 1.06, 1)

    # 共有トラック車隊(期ごとの全社台数上限): 全工場が競合するため
    # 全需要を賄うには足りるが、余裕は無い水準にする(タイトな共有資源)。
    fleet_size = np.maximum(2, np.ceil(total_dem_per_t / VEH_CAP * 0.90)).astype(int)
    # 労務時間の共有上限(台数枠とは独立にタイト): 平均的な便構成で使い切る水準
    avg_hours_per_veh = float(drive_hours.mean()) * 1.15
    labor_cap = np.round(fleet_size * avg_hours_per_veh, 1)

    return dict(nF=nF, nD=nD, nT=nT, prod_cost=prod_cost, setup_cost=setup_cost,
                prod_cap=prod_cap, inv_cap=inv_cap, hold_cost=hold_cost,
                ship_cost=ship_cost, veh_dispatch_cost=veh_dispatch_cost,
                drive_hours=drive_hours, labor_cap=labor_cap,
                demand=demand, fleet_size=fleet_size)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nF, nD, nT = d["nF"], d["nD"], d["nT"]
    prod_cost, setup_cost = d["prod_cost"], d["setup_cost"]
    prod_cap, inv_cap, hold_cost = d["prod_cap"], d["inv_cap"], d["hold_cost"]
    ship_cost, veh_dispatch_cost = d["ship_cost"], d["veh_dispatch_cost"]
    drive_hours, labor_cap = d["drive_hours"], d["labor_cap"]
    demand, fleet_size = d["demand"], d["fleet_size"]

    m = Model("Production_Distribution_Integrated")
    F, D, T = range(nF), range(nD), range(nT)

    # --- 変数 ---
    setup = {(f, t): m.addVar(vtype="B", name=f"setup_{f}_{t}") for f in F for t in T}
    prod = {(f, t): m.addVar(vtype="C", lb=0.0, ub=float(prod_cap[f]),
                             name=f"prod_{f}_{t}") for f in F for t in T}
    invF = {(f, t): m.addVar(vtype="C", lb=0.0, ub=float(inv_cap[f]),
                             name=f"invF_{f}_{t}") for f in F for t in T}
    ship = {(f, dd, t): m.addVar(vtype="C", lb=0.0, name=f"ship_{f}_{dd}_{t}")
            for f in F for dd in D for t in T}
    nveh = {(f, dd, t): m.addVar(vtype="I", lb=0, name=f"nveh_{f}_{dd}_{t}")
            for f in F for dd in D for t in T}
    # サードパーティ便バックストップ(高コスト): 常時実行可能性を担保
    backstop = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"backstop_{dd}_{t}")
                for dd in D for t in T}
    backstop_cost = float(ship_cost.max()) * 6.0

    # --- 制約 ---
    # 1. 段取り on/off: 生産は段取りした期のみ・タイトな生産能力上限
    #    (全工場合計でも需要をわずかに上回る程度=段取りタイミングと
    #    在庫の先行生産(時間結合)のトレードオフを強制する古典的ロットサイジング)
    for f in F:
        for t in T:
            m.addCons(prod[f, t] <= float(prod_cap[f]) * setup[f, t],
                      name=f"setup_gate_{f}_{t}")

    # 2. 工場在庫バランス(期跨ぎ、時間結合): I_ft = I_{f,t-1} + 生産 - 出荷
    for f in F:
        for t in T:
            prev = invF[f, t - 1] if t > 0 else 0.0
            m.addCons(
                invF[f, t] == prev + prod[f, t]
                - quicksum(ship[f, dd, t] for dd in D),
                name=f"inv_balance_{f}_{t}")

    # 3. トラック容量: 出荷量はトラック台数×積載上限まで
    for f in F:
        for dd in D:
            for t in T:
                m.addCons(ship[f, dd, t] <= VEH_CAP * nveh[f, dd, t],
                          name=f"veh_cap_{f}_{dd}_{t}")

    # 4. 共有トラック車隊(統合意思決定の核): 全工場が同一プールを取り合う
    for t in T:
        m.addCons(quicksum(nveh[f, dd, t] for f in F for dd in D)
                  <= int(fleet_size[t]), name=f"fleet_{t}")

    # 4b. 共有ドライバー労務時間(台数枠とは独立次元のタイトな共有資源):
    #     遠距離便ほど拘束時間が長く、単純な台数最小化では労務時間枠を超過しうる。
    #     台数枠・労務時間枠の同時タイト化が多次元ナップサック的な組合せ判断を強制する。
    for t in T:
        m.addCons(
            quicksum(float(drive_hours[f, dd]) * nveh[f, dd, t] for f in F for dd in D)
            <= float(labor_cap[t]), name=f"labor_{t}")

    # 5. DC需要充足: 各DCの受取(自社便+バックストップ) >= 需要
    for dd in D:
        for t in T:
            m.addCons(quicksum(ship[f, dd, t] for f in F) + backstop[dd, t]
                      >= float(demand[dd, t]), name=f"demand_{dd}_{t}")

    # --- 目的関数: 生産可変費+段取り固定費+在庫保管費+輸送費+車両発送費+バックストップ ---
    prod_var = quicksum(float(prod_cost[f]) * prod[f, t] for f in F for t in T)
    setup_fixed = quicksum(float(setup_cost[f]) * setup[f, t] for f in F for t in T)
    holding = quicksum(float(hold_cost[f]) * invF[f, t] for f in F for t in T)
    transport = quicksum(float(ship_cost[f, dd]) * ship[f, dd, t]
                         for f in F for dd in D for t in T)
    dispatch = quicksum(float(veh_dispatch_cost[f, dd]) * nveh[f, dd, t]
                        for f in F for dd in D for t in T)
    backstop_pen = quicksum(backstop_cost * backstop[dd, t] for dd in D for t in T)
    m.setObjective(prod_var + setup_fixed + holding + transport + dispatch + backstop_pen,
                   "minimize")

    m.data = {"setup": setup, "prod": prod, "invF": invF, "ship": ship,
              "nveh": nveh, "backstop": backstop, "scale": scale, "dims": (nF, nD, nT)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
