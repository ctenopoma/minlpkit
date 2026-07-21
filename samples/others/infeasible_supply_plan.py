"""過剰契約による実行不可能な生産・出荷計画 (Infeasible Supply Plan)

事業ストーリー
--------------
消費財メーカーの生産計画部門が、翌月の3製品(A/B/C)の生産量を決める。営業が結んだ
出荷契約(最低出荷量)を満たしつつ工場の能力内に収めたいが、営業の積み上げた契約合計が
工場の総生産能力を上回ってしまい、計画が組めない(実行不可能)。人はここで「どの制約を
緩めれば通るか」を怪しい制約のOn/Off・緩和で探す。その犯人特定を自動化する題材。

各制約の業務的意味:
- **総生産能力**: 3製品の合計生産量は工場ラインの月間能力(100)を超えられない(``cap_total``)。
- **出荷契約(最低出荷量)**: 各製品に契約上の最低出荷量(各40)がある。合計120は能力100を
  超える過剰契約(``contract_A/B/C``)。どの2本(計80)なら能力内だが、3本揃うと超過する。
- **製品ミックス比率**: 段取りの都合で A は B の2倍までしか作れない(``mix_ratio``、充足可能)。
- **販路上限**: A は市場規模から80までしか出せない(``market_cap_A``、充足可能な緩い上限)。
- **ライン立上げの二値判断**: 生産するならラインを立ち上げる(``line_on``、緩いbig-MでMIP化)。

矛盾の核(IIS)は ``cap_total`` + ``contract_A`` + ``contract_B`` + ``contract_C`` の4本。
どれか1本を外すと実行可能になる(能力を上げる、あるいは契約を1つ落とせば通る)極小核。
mix_ratio / market_cap_A / line_on は充足可能で核に含まれない = 削除フィルタが自動で除外する。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

PRODUCTS = ["A", "B", "C"]
CAPACITY = 100.0                       # 工場の月間総生産能力
CONTRACT = {"A": 40.0, "B": 40.0, "C": 40.0}   # 最低出荷契約(合計120 > 能力100 = 過剰契約)
UNIT_MARGIN = {"A": 12.0, "B": 9.0, "C": 7.0}
MARKET_CAP_A = 80.0                    # A の販路上限(緩く、非拘束のデコイ)
FIXED_COST = 20.0                      # ライン立上げの固定費


def build_model() -> Model:
    """過剰契約で実行不可能になる生産・出荷計画モデルを返す。"""
    m = Model("infeasible_supply_plan")

    prod = {p: m.addVar(name=f"prod_{p}", lb=0.0, ub=CAPACITY) for p in PRODUCTS}
    on = m.addVar(name="line_on", vtype="B")

    # 総生産能力(核に入る上限)
    m.addCons(quicksum(prod[p] for p in PRODUCTS) <= CAPACITY, name="cap_total")

    # 出荷契約(最低出荷量)。合計120が能力100を超える過剰契約 → cap_total と3本揃って矛盾
    for p in PRODUCTS:
        m.addCons(prod[p] >= CONTRACT[p], name=f"contract_{p}")

    # 製品ミックス比率(A は B の2倍まで。充足可能なデコイ)
    m.addCons(prod["A"] <= 2.0 * prod["B"], name="mix_ratio")

    # 販路上限(緩い上限。充足可能なデコイ)
    m.addCons(prod["A"] <= MARKET_CAP_A, name="market_cap_A")

    # ライン立上げ連動(緩いbig-Mで on=1 を促すだけ。総量上限としては非拘束のデコイ)
    m.addCons(quicksum(prod[p] for p in PRODUCTS) <= 500.0 * on, name="line_on")

    m.setObjective(quicksum(UNIT_MARGIN[p] * prod[p] for p in PRODUCTS) - FIXED_COST * on,
                   "maximize")
    return m


if __name__ == "__main__":
    import minlpkit as mk

    m = build_model()
    m.hideOutput()
    m.optimize()
    print("status:", m.getStatus())

    res = mk.diagnose_infeasibility(build_model, time_limit=10)
    print("presolveで矛盾を証明:", res["presolve_infeasible"])
    print("IIS核:", res["iis_core"], "—", res["iis_note"])
    print("弾性緩和(スラック>0):")
    e = res["elastic"]
    for _, r in e[e["slack"] > 1e-7].iterrows():
        print(f"  {r['constraint']}({r['sense']}) slack={r['slack']:.2f}")
