"""多階層物流ネットワーク配送計画 (Multi-echelon Distribution).

サプライチェーン計画者が、工場から複数の中継倉庫を経て複数の顧客地域へ製品を
届ける多段階(多階層)物流ネットワークにおいて、各拠点間の輸送量とどの倉庫を
稼働させるかを、総費用(輸送費+倉庫稼働の固定費)最小で決める問題である。
倉庫は稼働させるかどうかで固定費(賃料・人員配置)が発生する二値決定であり、
稼働させない倉庫は経由させられない。工場の生産能力・倉庫の処理能力・顧客ごとの
需要という3段階の容量制約をすべて満たしながらフローを流す必要があり、
「近い倉庫を使うほど輸送費は安いが、稼働倉庫を絞るほど固定費は下がる」という
ネットワーク設計上のトレードオフが表現される。

scale ノブ:
    small   : 倉庫2 × 顧客3 (テスト用)
    default : 倉庫3 × 顧客4
    large   : 倉庫4 × 顧客6
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_wh=2, n_cust=3),
    "default": dict(n_wh=3, n_cust=4),
    "large":   dict(n_wh=4, n_cust=6),
}

FACTORY_CAP = 500.0


def _data(scale: str):
    cfg = SCALES[scale]
    nW, nC = cfg["n_wh"], cfg["n_cust"]
    rng = np.random.default_rng(20260724 + nW * 41 + nC * 7)

    cost_fw = rng.uniform(2.0, 5.0, nW)              # 工場->倉庫 単位輸送費
    cost_wc = rng.uniform(1.5, 6.0, size=(nW, nC))    # 倉庫->顧客 単位輸送費
    wh_cap = rng.uniform(150.0, 260.0, nW)            # 倉庫処理能力
    wh_fixed = rng.uniform(800.0, 1500.0, nW)         # 倉庫稼働固定費
    demand = rng.uniform(40.0, 90.0, nC)              # 顧客需要

    return dict(nW=nW, nC=nC, cost_fw=cost_fw, cost_wc=cost_wc, wh_cap=wh_cap,
                wh_fixed=wh_fixed, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nW, nC = d["nW"], d["nC"]
    cost_fw, cost_wc = d["cost_fw"], d["cost_wc"]
    wh_cap, wh_fixed, demand = d["wh_cap"], d["wh_fixed"], d["demand"]

    model = Model("Multi_Echelon_Distribution")
    W, C = range(nW), range(nC)

    x_fw = {w: model.addVar(vtype="C", lb=0.0, name=f"x_fw_{w}") for w in W}
    x_wc = {(w, c): model.addVar(vtype="C", lb=0.0, name=f"x_wc_{w}_{c}") for w in W for c in C}
    open_wh = {w: model.addVar(vtype="B", name=f"open_{w}") for w in W}

    model.addCons(quicksum(x_fw[w] for w in W) <= FACTORY_CAP, name="factory_cap")

    for w in W:
        model.addCons(
            x_fw[w] == quicksum(x_wc[w, c] for c in C), name=f"warehouse_flow_{w}")
        model.addCons(x_fw[w] <= float(wh_cap[w]) * open_wh[w], name=f"warehouse_cap_{w}")

    for c in C:
        model.addCons(quicksum(x_wc[w, c] for w in W) >= float(demand[c]), name=f"demand_{c}")

    transport = (
        quicksum(float(cost_fw[w]) * x_fw[w] for w in W)
        + quicksum(float(cost_wc[w, c]) * x_wc[w, c] for w in W for c in C))
    fixed = quicksum(float(wh_fixed[w]) * open_wh[w] for w in W)
    model.setObjective(transport + fixed, "minimize")

    model.data = {"x_fw": x_fw, "x_wc": x_wc, "open_wh": open_wh,
                  "scale": scale, "dims": (nW, nC)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
