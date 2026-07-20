"""多段階在庫計画(工場→DC→小売、リードタイム跨ぎ+安全在庫) (Realistic Multi-Echelon Inventory).

事業ストーリー
--------------
サプライチェーン計画者が、単一工場から複数の配送センター(DC)を経て複数の
小売店へ商品を補充する3段階在庫網について、各段の発注量(整数ロット)・
安全在庫の維持・欠品時の機会損失を週次で計画する意思決定である。
既存の `multi_echelon_distribution.py` は単一期の純フロー配分問題だが、
本モデルは**時間結合(リードタイム跨ぎの発注-到着ズレ)**と
**整数ロット発注**という現実の補充運用そのものを扱う点で別物である。

各制約の業務的意味:
- **DCの整数ロット発注(工場へ)**: DCは工場に対し、決まったロットサイズの
  倍数でしか発注できない(パレット単位・最小ロット規約)。発注した期には
  段取り的な発送固定費がかかる(バイナリ `order_on[d,t]`)。
- **工場の生産能力(共有リソース、統合意思決定)**: 工場の週間生産能力は
  全DCで共有され、`sum_d order_dc[d,t] <= factory_cap[t]` という単一の
  制約で複数DCの発注が結合する(あるDCが多く発注すれば他DCの枠が減る)。
- **リードタイム跨ぎの在庫バランス(時間結合)**: DCが期tに発注した量は
  即座には届かず、`t + lead_dc[d]` 期後に到着する(輸送・検品にかかる
  時間)。これにより発注の意思決定と在庫水準の変化が時間的にズレて結合し、
  期を独立に最適化できなくなる(=期分解を妨げる本質的な時間結合)。
- **小売店の整数ロット発注(DCへ)**: 各小売店は担当DCに対し、同様に
  整数ロット単位で発注し、DC→小売のリードタイム後に届く。
- **安全在庫(ソフト制約)**: DC・小売それぞれに安全在庫水準の目標があり、
  下回るとペナルティが発生する(欠品リスクの機会費用としての罰金であり、
  ハード制約にはしない=常時実行可能性を担保)。
- **欠品(ロスト・セールス)ペナルティ**: 小売の需要は当期の在庫+到着分で
  賄えない場合、機会損失として高コストのペナルティを払う(バックストップ)。
- **DCの緊急補充バックストップ**: 小売の発注量はDCの手持ち在庫に関わらず
  ロット単位で確定するため(現実には小売側の発注意思決定はDCの在庫可視性を
  完全には持たない)、DC側が不足すれば高コストの特急便で穴埋めする。
  常時実行可能性を担保する現実の逃げ道。

なぜ結合が業務要件として自然に入るか:
現実の多段階補充網では、上流(工場)の生産能力は複数の下流拠点(DC)で
取り合いになり、かつ発注してから届くまでのリードタイムがあるため
「今何を発注すべきか」は「将来何期か先まで在庫が持つか」という時間結合の
見通しに依存する。これは分離不可能であり、単純な当期需要=当期発注の
教科書モデルでは再現できない現実の硬さである。

scale ノブ(硬さの源泉: 現実規模 + 統合意思決定(共有工場能力) + 時間結合(リードタイム)):
    small   : DC2 × 小売(DC毎2店=計4) × 期4   (テスト・ハンズオン用。数分で最適)
    default : DC4 × 小売(DC毎3店=計12) × 期8  (診断の題材)
    large   : DC5 × 小売(DC毎4店=計20) × 期10
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_dc=2, n_ret_per_dc=2, n_t=4),
    "default": dict(n_dc=4, n_ret_per_dc=3, n_t=8),
    "large":   dict(n_dc=5, n_ret_per_dc=4, n_t=10),
}


def _data(scale: str):
    cfg = SCALES[scale]
    nD, nRpD, nT = cfg["n_dc"], cfg["n_ret_per_dc"], cfg["n_t"]
    nR = nD * nRpD
    rng = np.random.default_rng(20260720 + nD * 53 + nRpD * 11 + nT * 3)

    # 小売 r の担当DC(固定トポロジ): r // nRpD
    dc_of = np.array([r // nRpD for r in range(nR)])

    # DC発注(工場から): ロットサイズ・リードタイム・発送固定費・可変費
    lot_dc = np.round(rng.uniform(15.0, 30.0, nD), 1)
    lead_dc = rng.integers(1, 3, nD)                      # 1-2期
    order_fixed_dc = np.round(rng.uniform(120.0, 260.0, nD), 1)
    order_var_dc = np.round(rng.uniform(6.0, 10.0, nD), 2)
    dc_max_lots = 6  # 1期あたり最大ロット数(過大発注の防止)

    # 小売発注(DCから): ロットサイズ・リードタイム・発送固定費・可変費
    lot_r = np.round(rng.uniform(4.0, 9.0, nR), 1)
    lead_r = rng.integers(1, 2, nR)                        # 1期
    order_fixed_r = np.round(rng.uniform(20.0, 50.0, nR), 1)
    order_var_r = np.round(rng.uniform(9.0, 14.0, nR), 2)
    r_max_lots = 5

    # 工場の週間生産能力(共有リソース、複数DCが取り合う)
    dc_avg_need = (lot_dc * dc_max_lots * 0.55).sum()
    factory_cap = np.round(np.full(nT, dc_avg_need * 0.60), 1)

    # 需要(小売、山谷)
    base_dem = rng.uniform(3.0, 7.0, nR)
    season = 1.0 + 0.30 * np.sin(np.linspace(0.2, 3.3, nT))
    demand = np.round(np.outer(base_dem, season) + rng.uniform(-0.8, 0.8, (nR, nT)), 2)
    demand = np.maximum(demand, 0.5)

    # 安全在庫目標・保管費・欠品/安全在庫割れペナルティ
    safety_dc = np.round(lot_dc * 0.8, 1)
    safety_r = np.round(lot_r * 0.8, 1)
    hold_dc = np.round(rng.uniform(0.3, 0.6, nD), 2)
    hold_r = np.round(rng.uniform(0.5, 0.9, nR), 2)
    safety_pen_dc = np.round(rng.uniform(8.0, 15.0, nD), 1)
    safety_pen_r = np.round(rng.uniform(8.0, 15.0, nR), 1)
    lost_sales_pen = np.round(rng.uniform(60.0, 100.0, nR), 1)

    # 初期在庫(安全在庫水準あたりから開始)
    inv0_dc = safety_dc.copy()
    inv0_r = safety_r.copy()

    return dict(nD=nD, nR=nR, nT=nT, dc_of=dc_of, lot_dc=lot_dc, lead_dc=lead_dc,
                order_fixed_dc=order_fixed_dc, order_var_dc=order_var_dc,
                dc_max_lots=dc_max_lots, lot_r=lot_r, lead_r=lead_r,
                order_fixed_r=order_fixed_r, order_var_r=order_var_r,
                r_max_lots=r_max_lots, factory_cap=factory_cap, demand=demand,
                safety_dc=safety_dc, safety_r=safety_r, hold_dc=hold_dc,
                hold_r=hold_r, safety_pen_dc=safety_pen_dc,
                safety_pen_r=safety_pen_r, lost_sales_pen=lost_sales_pen,
                inv0_dc=inv0_dc, inv0_r=inv0_r)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nD, nR, nT = d["nD"], d["nR"], d["nT"]
    dc_of = d["dc_of"]
    lot_dc, lead_dc = d["lot_dc"], d["lead_dc"]
    order_fixed_dc, order_var_dc = d["order_fixed_dc"], d["order_var_dc"]
    dc_max_lots = d["dc_max_lots"]
    lot_r, lead_r = d["lot_r"], d["lead_r"]
    order_fixed_r, order_var_r = d["order_fixed_r"], d["order_var_r"]
    r_max_lots = d["r_max_lots"]
    factory_cap, demand = d["factory_cap"], d["demand"]
    safety_dc, safety_r = d["safety_dc"], d["safety_r"]
    hold_dc, hold_r = d["hold_dc"], d["hold_r"]
    safety_pen_dc, safety_pen_r = d["safety_pen_dc"], d["safety_pen_r"]
    lost_sales_pen = d["lost_sales_pen"]
    inv0_dc, inv0_r = d["inv0_dc"], d["inv0_r"]

    m = Model("Multi_Echelon_Inventory_Realistic")
    D, R, T = range(nD), range(nR), range(nT)
    retails_of = {dd: [r for r in R if dc_of[r] == dd] for dd in D}

    # --- 変数 ---
    # DC発注: 整数ロット数(工場から)
    n_dc = {(dd, t): m.addVar(vtype="I", lb=0, ub=dc_max_lots, name=f"ndc_{dd}_{t}")
            for dd in D for t in T}
    order_on_dc = {(dd, t): m.addVar(vtype="B", name=f"orderon_dc_{dd}_{t}")
                   for dd in D for t in T}
    inv_dc = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"inv_dc_{dd}_{t}")
              for dd in D for t in T}
    short_dc = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"short_dc_{dd}_{t}")
                for dd in D for t in T}

    # 小売発注: 整数ロット数(担当DCから)
    n_r = {(r, t): m.addVar(vtype="I", lb=0, ub=r_max_lots, name=f"nr_{r}_{t}")
           for r in R for t in T}
    order_on_r = {(r, t): m.addVar(vtype="B", name=f"orderon_r_{r}_{t}")
                  for r in R for t in T}
    inv_r = {(r, t): m.addVar(vtype="C", lb=0.0, name=f"inv_r_{r}_{t}")
             for r in R for t in T}
    short_r = {(r, t): m.addVar(vtype="C", lb=0.0, name=f"short_r_{r}_{t}")
               for r in R for t in T}
    lost = {(r, t): m.addVar(vtype="C", lb=0.0, name=f"lost_{r}_{t}") for r in R for t in T}

    # DCから小売への出荷量(DC在庫の払い出し、リードタイムはr側で管理)
    ship_r = {(r, t): m.addVar(vtype="C", lb=0.0, name=f"shipr_{r}_{t}")
              for r in R for t in T}
    # DCの緊急補充(工場からの通常発注のリードタイムをバイパスする高コスト特急便):
    # 小売の発注はDCの手持ち在庫を問わず一致させる設計のため、DCの在庫バランスが
    # 負にならないための常時実行可能性バックストップとして必須
    emerg_dc = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"emerg_dc_{dd}_{t}")
                for dd in D for t in T}

    # --- 制約 ---
    # 1. DC発注量 = ロットサイズ×ロット数、発注固定費のon/offゲート
    for dd in D:
        for t in T:
            m.addCons(n_dc[dd, t] <= dc_max_lots * order_on_dc[dd, t],
                      name=f"gate_dc_{dd}_{t}")

    # 2. 工場の共有生産能力(統合意思決定): 全DCの発注が同一制約で結合
    for t in T:
        m.addCons(
            quicksum(float(lot_dc[dd]) * n_dc[dd, t] for dd in D)
            <= float(factory_cap[t]), name=f"factory_cap_{t}")

    # 3. DC在庫バランス(リードタイム跨ぎ、時間結合):
    #    到着 = t - lead_dc[d] 期に発注した量(それより前は初期パイプライン無し)
    for dd in D:
        for t in T:
            arr_t = t - int(lead_dc[dd])
            arrival = (float(lot_dc[dd]) * n_dc[dd, arr_t]) if arr_t >= 0 else 0.0
            prev = inv_dc[dd, t - 1] if t > 0 else float(inv0_dc[dd])
            outflow = quicksum(ship_r[r, t] for r in retails_of[dd])
            m.addCons(inv_dc[dd, t] == prev + arrival + emerg_dc[dd, t] - outflow,
                      name=f"balance_dc_{dd}_{t}")
            # 安全在庫割れの不足量(ソフト制約)
            m.addCons(short_dc[dd, t] >= float(safety_dc[dd]) - inv_dc[dd, t],
                      name=f"safety_dc_{dd}_{t}")

    # 4. 小売発注量 = ロットサイズ×ロット数、発注固定費のon/offゲート
    for r in R:
        for t in T:
            m.addCons(n_r[r, t] <= r_max_lots * order_on_r[r, t],
                      name=f"gate_r_{r}_{t}")
            # DCからの出荷は小売の発注量に一致(DC在庫を持つ在庫点として払い出す)
            m.addCons(ship_r[r, t] == float(lot_r[r]) * n_r[r, t],
                      name=f"ship_eq_order_{r}_{t}")

    # 5. 小売在庫バランス(リードタイム跨ぎ)+ 需要充足(欠品=lost sales)
    for r in R:
        for t in T:
            arr_t = t - int(lead_r[r])
            arrival = (float(lot_r[r]) * n_r[r, arr_t]) if arr_t >= 0 else 0.0
            prev = inv_r[r, t - 1] if t > 0 else float(inv0_r[r])
            # 在庫-欠品(lost sales)の同時決定式: inv - lost = 前期在庫+到着-需要。
            # inv・lost とも >=0 かつ lost には高額ペナルティがあるため、最適解では
            # 需要を賄えるうちは inv=net>=0・lost=0、賄えなければ inv=0・lost=-net
            # という現実の需要充足の挙動が自動的に再現される。
            m.addCons(
                inv_r[r, t] - lost[r, t] == prev + arrival - float(demand[r, t]),
                name=f"balance_r_{r}_{t}")
            m.addCons(short_r[r, t] >= float(safety_r[r]) - inv_r[r, t],
                      name=f"safety_r_{r}_{t}")

    # --- 目的関数 ---
    order_cost_dc = quicksum(
        float(order_fixed_dc[dd]) * order_on_dc[dd, t]
        + float(order_var_dc[dd]) * float(lot_dc[dd]) * n_dc[dd, t]
        for dd in D for t in T)
    order_cost_r = quicksum(
        float(order_fixed_r[r]) * order_on_r[r, t]
        + float(order_var_r[r]) * float(lot_r[r]) * n_r[r, t]
        for r in R for t in T)
    holding = (quicksum(float(hold_dc[dd]) * inv_dc[dd, t] for dd in D for t in T)
               + quicksum(float(hold_r[r]) * inv_r[r, t] for r in R for t in T))
    safety_pen = (quicksum(float(safety_pen_dc[dd]) * short_dc[dd, t] for dd in D for t in T)
                  + quicksum(float(safety_pen_r[r]) * short_r[r, t] for r in R for t in T))
    lost_pen = quicksum(float(lost_sales_pen[r]) * lost[r, t] for r in R for t in T)
    emerg_cost = float(order_var_dc.max()) * 8.0
    emerg_pen = quicksum(emerg_cost * emerg_dc[dd, t] for dd in D for t in T)
    m.setObjective(order_cost_dc + order_cost_r + holding + safety_pen + lost_pen + emerg_pen,
                   "minimize")

    m.data = {"n_dc": n_dc, "n_r": n_r, "inv_dc": inv_dc, "inv_r": inv_r,
              "lost": lost, "emerg_dc": emerg_dc, "scale": scale, "dims": (nD, nR, nT)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
