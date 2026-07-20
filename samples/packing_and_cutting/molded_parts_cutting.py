"""射出成形型替え・製造スケジュール (Molded Parts Setup Optimization).

射出成形工場の生産計画者が、複数種類の部品(金型)を複数期間(週次生産計画)に
わたってどの金型を使うか、また金型を切り替える(段取り替え)かどうかを、
段取り替えコストと納期遵守を両立するように決める生産計画問題である。金型の
切り替えには段取り替え時間・費用がかかるため、前期から同じ金型を使い続ける
方が有利だが、各部品には需要(納期までに満たすべき数量)があり、需要を満たす
ためにはどこかで金型を切り替えざるを得ない。ロットサイズ(生産数量、整数の
バッチ単位)と段取り替えの有無(整数)を同時に決めることで、切替コストと
在庫保管コストのトレードオフが表現される。

scale ノブ:
    small   : 部品3 × 期3 (テスト用)
    default : 部品4 × 期5
    large   : 部品5 × 期6
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_part=3, n_t=3),
    "default": dict(n_part=4, n_t=5),
    "large":   dict(n_part=5, n_t=6),
}

SETUP_COST = 150.0       # 金型切替の段取り替えコスト[$]
HOLDING_COST = 3.0       # 在庫保管コスト[$/個/期]
LOT_SIZE = 20            # 1ロットあたりの生産数量(整数バッチ単位)
LOT_CAP_PER_PART = 3     # 部品1種あたりの1期の最大ロット数(機械稼働時間の制約の元)


def _data(scale: str):
    cfg = SCALES[scale]
    nI, nT = cfg["n_part"], cfg["n_t"]
    rng = np.random.default_rng(20260724 + nI * 37 + nT * 13)

    demand = rng.integers(15, 45, size=(nI, nT))
    return dict(nI=nI, nT=nT, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nI, nT, demand = d["nI"], d["nT"], d["demand"]
    # 機械の1期あたり総ロット数上限(部品種数に比例させ、需要規模とバランスさせる)
    machine_lot_cap = LOT_CAP_PER_PART * nI

    model = Model("Molded_Parts_Setup")
    I, T = range(nI), range(nT)

    lots = {(i, t): model.addVar(vtype="I", lb=0, ub=machine_lot_cap, name=f"lots_{i}_{t}")
            for i in I for t in T}
    use = {(i, t): model.addVar(vtype="B", name=f"use_{i}_{t}") for i in I for t in T}
    setup = {(i, t): model.addVar(vtype="B", name=f"setup_{i}_{t}") for i in I for t in T}
    inv = {(i, t): model.addVar(vtype="C", lb=0.0, name=f"inv_{i}_{t}") for i in I for t in T}

    for t in T:
        # 機械は1期あたり生産可能なロット総数に上限(稼働時間制約)
        model.addCons(quicksum(lots[i, t] for i in I) <= machine_lot_cap, name=f"machine_cap_{t}")
        for i in I:
            model.addCons(lots[i, t] <= machine_lot_cap * use[i, t], name=f"onoff_{i}_{t}")
            prev_use = use[i, t - 1] if t > 0 else 0
            model.addCons(setup[i, t] >= use[i, t] - prev_use, name=f"setup_def_{i}_{t}")
            prev_inv = inv[i, t - 1] if t > 0 else 0.0
            model.addCons(
                inv[i, t] == prev_inv + LOT_SIZE * lots[i, t] - float(demand[i, t]),
                name=f"inv_balance_{i}_{t}")

    setup_total = quicksum(SETUP_COST * setup[i, t] for i in I for t in T)
    holding_total = quicksum(HOLDING_COST * inv[i, t] for i in I for t in T)
    model.setObjective(setup_total + holding_total, "minimize")
    model.data = {"lots": lots, "use": use, "setup": setup, "inv": inv,
                  "scale": scale, "dims": (nI, nT)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Setup Cost:", m.getObjVal())


if __name__ == "__main__":
    main()
