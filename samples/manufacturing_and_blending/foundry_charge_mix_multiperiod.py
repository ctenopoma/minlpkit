"""鋳造の多期チャージ配合計画 (Multi-period Foundry Charge Mix).

事業ストーリー
--------------
電気炉(EAF)を持つ鋳物工場の「溶解計画係」が、数日〜1週間の計画期間について、
各時間帯(期)に「どの注文グレードの溶湯を、何回(整数)、1回あたり何トン(連続)溶かし、
その各チャージにスクラップ在庫のどのロットを何トン投入するか」を決める意思決定である。

既存の易しい版 `foundry_charge_mix.py`(単一チャージ・2原料の配合)を、
多期・複数注文・在庫品質ばらつき・電力時間帯料金まで精緻化したもの。

各制約の業務的意味:
- **ヒート回数(整数)× ヒートサイズ(連続)= 溶解量(双線形)**: 電気炉は1回の溶解(ヒート)
  ごとに段取り(通電立上げ・出湯)が要る離散操作なので回数は整数。1ヒートの装入量は
  炉容量の範囲で連続。よって期ごとの溶解量 = 回数 × サイズ の**整数×連続の積**。
- **スクラップ在庫の品質ばらつき(ロット別成分)**: 回収スクラップはロットごとに炭素・銅の
  含有率が異なり在庫量も限られる。銅は精錬で除去できないため、高銅スクラップの使用量が
  グレード上限で縛られる(トランプエレメント問題)。在庫は全期で共有(時間結合)。
- **溶湯組成 = 装入配合の加重平均(双線形=よく撹拌された1ヒート)**: その期の溶湯の炭素/銅
  濃度は変数で、装入ロットの成分質量 = 濃度 × 溶解量 で決まる(**濃度×質量の双線形**)。
  1つの溶湯を複数注文へ配分するので、同じ期に打つ注文はグレード窓が重なっていなければならず、
  注文が共通の溶湯組成を通じて結合する(プーリング型の強い非凸)。
- **成分規格(双線形)**: 注文へ配分する溶湯は、その注文の炭素規格窓 [下限,上限] と銅上限を
  満たす。配分量 × (濃度−規格) の形で効く。
- **注文の納期**: 各注文はグレード・数量・納期を持ち、納期までの累積配分(+外注)が数量以上。
- **電力の時間帯料金**: 期ごとに電力単価が異なり(夜間安・昼間高)、溶解の電力費は
  溶解量 × 単価。安い時間帯にまとめて溶かす誘因が生まれる(時間結合)。
- **外注バックストップ(高コスト)**: 自社溶解で納期を満たせない分は規格適合品を外注購入で
  充足できる(常に実行可能性を担保。最適解では割高な外注より自社溶解が選ばれる)。

なぜ非凸が業務要件として自然に入るか:
「離散的なヒート回数 × 連続的なヒートサイズ」と「よく撹拌された溶湯の濃度 × 質量/配分量」という
炉の運転実態そのものが双線形を生む。溶湯組成が注文間で共有される結合(プーリング型)により
双線形が互いに絡み合い、SCIP の McCormick 緩和では双対境界が伸びず gap が残る。診断で
weak_relaxation / wide_term_range が題材になる(FINDINGS 3節の厳密線形化・区分線形化が候補)。

scale ノブ(硬さの源泉: 現実規模 + 物理結合(整数×連続・濃度×質量)+ 時間結合(在庫・納期)):
    small   : ロット3 × 注文2 × 期3   (テスト・ハンズオン用。数分で最適)
    default : ロット8 × 注文5 × 期6   (診断の題材。30秒でgap残存)
    large   : ロット12 × 注文7 × 期8
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_lot=3, n_order=2, n_period=3),
    "default": dict(n_lot=12, n_order=8, n_period=8),
    "large":   dict(n_lot=15, n_order=10, n_period=10),
}

# 炉の運転パラメータ
HEAT_MIN, HEAT_MAX = 5.0, 30.0     # 1ヒートのサイズ範囲 [トン]
N_HEAT_MAX = 4                     # 期・注文あたり最大ヒート回数
ENERGY_PER_TON = 0.55             # MWh/トン(電気炉の比エネルギー)


def _data(scale: str):
    cfg = SCALES[scale]
    nI, nO, nT = cfg["n_lot"], cfg["n_order"], cfg["n_period"]
    rng = np.random.default_rng(770077 + nI * 101 + nO * 31 + nT * 7)

    # スクラップロット: 炭素%・銅%(トランプエレメント)・在庫量・単価
    carbon = np.round(rng.uniform(0.05, 3.8, nI), 3)          # 低炭素鋼屑〜高炭素銑
    copper = np.round(rng.uniform(0.02, 0.55, nI), 3)         # 銅不純物
    lot_inv = np.round(rng.uniform(12, 30, nI), 1)            # ロット在庫[トン](希少)
    # 単価: 低銅(クリーン)ほど高い。高炭素銑鉄も高め
    lot_cost = np.round(160 + 120 * (0.55 - copper) + 25 * carbon
                        + rng.uniform(-15, 15, nI), 1)

    # 注文: 炭素規格窓(狭く=期の溶湯を専用化させ結合を強める)・銅上限(タイト)・数量・納期
    c_lo = np.round(rng.uniform(0.15, 1.4, nO), 3)
    c_hi = np.round(c_lo + rng.uniform(0.15, 0.30, nO), 3)
    cu_max = np.round(rng.uniform(0.12, 0.22, nO), 3)
    qty = np.round(rng.uniform(20, 60, nO), 1)
    due = rng.integers(1, nT + 1, nO)                        # 1..nT
    heat_fixed = np.round(rng.uniform(40, 90, nO), 1)        # ヒート段取り固定費

    # 電力時間帯料金(夜間安・昼間高の山谷)[$/MWh]
    price = np.round(55 + 35 * np.sin(np.linspace(-1.2, 2.4, nT))
                     + rng.uniform(-5, 5, nT), 1)
    price = np.maximum(price, 20.0)

    return dict(nI=nI, nO=nO, nT=nT, carbon=carbon, copper=copper,
                lot_inv=lot_inv, lot_cost=lot_cost, c_lo=c_lo, c_hi=c_hi,
                cu_max=cu_max, qty=qty, due=due, heat_fixed=heat_fixed,
                price=price)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nI, nO, nT = d["nI"], d["nO"], d["nT"]
    carbon, copper = d["carbon"], d["copper"]
    lot_inv, lot_cost = d["lot_inv"], d["lot_cost"]
    c_lo, c_hi, cu_max = d["c_lo"], d["c_hi"], d["cu_max"]
    qty, due, heat_fixed = d["qty"], d["due"], d["heat_fixed"]
    price = d["price"]

    m = Model("Foundry_Charge_Mix_MultiPeriod")

    I = range(nI); O = range(nO); T = range(nT)
    c_min, c_max = float(carbon.min()), float(carbon.max())
    cu_min_lot, cu_max_lot = float(copper.min()), float(copper.max())

    # --- 変数 ---
    # ヒート回数(整数)× ヒートサイズ(連続)= 期の溶解量(双線形・整数×連続)
    n = {t: m.addVar(vtype="I", lb=0, ub=N_HEAT_MAX, name=f"n_{t}") for t in T}
    s = {t: m.addVar(vtype="C", lb=0.0, ub=HEAT_MAX, name=f"s_{t}") for t in T}
    melt = {t: m.addVar(vtype="C", lb=0.0, ub=N_HEAT_MAX * HEAT_MAX,
                        name=f"melt_{t}") for t in T}
    # ロット i を 期t のヒートへ投入する量[トン]
    c = {(i, t): m.addVar(vtype="C", lb=0.0, ub=float(lot_inv[i]), name=f"c_{i}_{t}")
         for i in I for t in T}
    # 溶湯組成(変数): 炭素・銅の濃度
    cc = {t: m.addVar(vtype="C", lb=c_min, ub=c_max, name=f"cc_{t}") for t in T}
    cu = {t: m.addVar(vtype="C", lb=cu_min_lot, ub=cu_max_lot, name=f"cu_{t}")
          for t in T}
    # 期t の溶湯を 注文o へ配分する量[トン]
    g = {(o, t): m.addVar(vtype="C", lb=0.0, ub=N_HEAT_MAX * HEAT_MAX,
                          name=f"g_{o}_{t}") for o in O for t in T}
    # 外注バックストップ(規格適合・高コスト)
    out = {(o, t): m.addVar(vtype="C", lb=0.0, name=f"out_{o}_{t}")
           for o in O for t in T}
    out_cost = float(lot_cost.max()) * 3.0

    # --- 制約 ---
    # 1. 溶解量 = ヒート回数 × ヒートサイズ(双線形・整数×連続)
    for t in T:
        m.addCons(melt[t] == n[t] * s[t], name=f"melt_def_{t}")

    # 2. チャージ質量収支: 投入ロット合計 = 溶解量
    for t in T:
        m.addCons(quicksum(c[i, t] for i in I) == melt[t], name=f"charge_mass_{t}")

    # 3. 溶湯組成の定義(双線形: 濃度 × 溶解量 = 装入成分の質量)
    for t in T:
        m.addCons(quicksum(float(carbon[i]) * c[i, t] for i in I) == cc[t] * melt[t],
                  name=f"carbon_bal_{t}")
        m.addCons(quicksum(float(copper[i]) * c[i, t] for i in I) == cu[t] * melt[t],
                  name=f"copper_bal_{t}")

    # 4. 溶湯の配分収支: 期tの溶解量を注文へ配分
    for t in T:
        m.addCons(quicksum(g[o, t] for o in O) == melt[t], name=f"alloc_{t}")

    # 5. 成分規格(双線形: 配分量 × 濃度)。配分がある注文はグレード窓・銅上限を満たす
    for o in O:
        for t in T:
            m.addCons(cc[t] * g[o, t] >= float(c_lo[o]) * g[o, t], name=f"carb_lo_{o}_{t}")
            m.addCons(cc[t] * g[o, t] <= float(c_hi[o]) * g[o, t], name=f"carb_hi_{o}_{t}")
            m.addCons(cu[t] * g[o, t] <= float(cu_max[o]) * g[o, t], name=f"cu_hi_{o}_{t}")

    # 6. ロット在庫上限(全期で消費した合計 <= 在庫)
    for i in I:
        m.addCons(quicksum(c[i, t] for t in T) <= float(lot_inv[i]),
                  name=f"lot_inv_{i}")

    # 7. 納期充足: 納期までの累積配分(+外注) >= 数量
    for o in O:
        d_o = int(due[o])
        m.addCons(
            quicksum(g[o, t] + out[o, t] for t in range(d_o)) >= float(qty[o]),
            name=f"due_{o}")

    # --- 目的関数: スクラップ費 + 電力費(時間帯料金)+ ヒート段取り費 + 外注費 ---
    scrap_cost = quicksum(float(lot_cost[i]) * c[i, t] for i in I for t in T)
    power_cost = quicksum(ENERGY_PER_TON * float(price[t]) * melt[t] for t in T)
    setup_cost = quicksum(float(heat_fixed[o]) for o in O) / nO \
        * quicksum(n[t] for t in T)
    outsource = quicksum(out_cost * out[o, t] for o in O for t in T)
    m.setObjective(scrap_cost + power_cost + setup_cost + outsource, "minimize")

    m.data = {"n": n, "s": s, "melt": melt, "c": c, "cc": cc, "cu": cu,
              "g": g, "out": out, "scale": scale, "dims": (nI, nO, nT)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
