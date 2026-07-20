"""飲料ボトリングライン段取り最適化 (Beverage Bottling Line Scheduling)

事業ストーリー
--------------
飲料メーカーの生産計画担当者が、1本のボトリングラインで複数SKU(製品銘柄・容量違い)を
どのシフトにどれだけ生産するかを決める。SKUを切り替えるたびに殺菌・充填ラインの
洗浄(CIP)段取りが発生し稼働時間を圧迫するため、切替回数を抑えつつ各SKUの需要を
満たす生産計画を立てる必要がある。

各制約の業務的意味:
- **シフトごとに稼働できるSKUは1つ**: ライン自体は1系統しかなく、同時に複数SKUは
  流せない。
- **生産量はSKUが稼働しているシフトでのみ発生**: 稼働していないSKUの生産量は0
  (二値の稼働フラグに連動する容量制約、いわゆる semi-continuous)。
- **SKUごとの需要充足**: 全シフトを通じた生産量合計が需要を満たす必要がある。
- **切替検知(段取りコスト)**: 直前シフトと異なるSKUを立ち上げたシフトでは
  切替フラグが立ち、段取り時間分のコストが加算される。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

SKUS = ["cola_500ml", "cola_1500ml", "juice_500ml"]
N_SHIFTS = 3
SHIFT_CAPACITY = 6500       # 1シフトの生産能力上限(本)
DEMAND = {"cola_500ml": 6000, "cola_1500ml": 3500, "juice_500ml": 2500}
CHANGEOVER_COST = 300


def build_model():
    model = Model("Beverage_Bottling_Line")

    run = {(k, t): model.addVar(vtype="B", name=f"run_{k}_{t}")
           for k in SKUS for t in range(N_SHIFTS)}
    qty = {(k, t): model.addVar(vtype="C", lb=0, name=f"qty_{k}_{t}")
           for k in SKUS for t in range(N_SHIFTS)}
    change = {t: model.addVar(vtype="B", name=f"ch_{t}") for t in range(1, N_SHIFTS)}

    for t in range(N_SHIFTS):
        model.addCons(quicksum(run[k, t] for k in SKUS) <= 1, f"one_sku_{t}")

    for k in SKUS:
        for t in range(N_SHIFTS):
            model.addCons(qty[k, t] <= SHIFT_CAPACITY * run[k, t], f"cap_link_{k}_{t}")
        model.addCons(quicksum(qty[k, t] for t in range(N_SHIFTS)) >= DEMAND[k],
                       f"demand_{k}")

    for t in range(1, N_SHIFTS):
        for k in SKUS:
            model.addCons(change[t] >= run[k, t] - run[k, t - 1], f"changeover_{k}_{t}")

    total_cost = CHANGEOVER_COST * quicksum(change[t] for t in range(1, N_SHIFTS))
    model.setObjective(total_cost, "minimize")
    model.data = {"run": run, "qty": qty, "change": change}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Setup Cost:", m.getObjVal())
