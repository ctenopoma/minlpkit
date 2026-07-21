"""空港フライト・ゲート自動割当 (Airport Gate Assignment)

事業ストーリー
--------------
空港の地上運航管理者(グランドオペレーション)が、当日の到着便をどのゲートに割り当てるかを
決める。ゲートは機材サイズ(ワイドボディ対応可否)で制約があり、割り当てられなかった便は
リモートスポット(バス移動)に回されるが乗客満足度が下がる。

各制約の業務的意味:
- **便ごとに割当先はゲートかリモートのいずれか一つ**: 二重割当も割当漏れも許されない。
- **ゲートは同時刻帯に1便まで**: 同じタイムスロットで同一ゲートに複数便を割り当てられない
  (旋回・清掃時間を考慮した物理的な排他制約)。
- **機材適合性**: ワイドボディ機は対応ゲート(ボーディングブリッジ規格)にしか着けられない。
- **リモートスポットは常に受入可能(逃げ道)**: ゲートが不足しても運航自体は継続できるよう、
  コストは高いがリモート駐機は常に選択できる。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

FLIGHTS = ["F1", "F2", "F3", "F4", "F5", "F6"]
GATES = ["G1", "G2", "G3", "G4"]

# 便の到着タイムスロット(同スロット・同ゲートは排他)
SLOT = {"F1": 0, "F2": 0, "F3": 1, "F4": 1, "F5": 2, "F6": 2}
# ワイドボディ機かどうか
WIDE_BODY = {"F1": True, "F2": False, "F3": False, "F4": True, "F5": False, "F6": False}
WIDE_GATES = {"G1", "G2"}   # ブリッジ規格上ワイドボディに対応できるゲート

# ゲート割当の乗客満足度スコア(近い・便利なゲートほど高得点)、リモートは低得点
SATISFACTION = {
    ("F1", "G1"): 100, ("F1", "G2"): 90,
    ("F2", "G1"): 80, ("F2", "G2"): 85, ("F2", "G3"): 95, ("F2", "G4"): 70,
    ("F3", "G3"): 100, ("F3", "G4"): 88,
    ("F4", "G1"): 92, ("F4", "G2"): 96,
    ("F5", "G3"): 90, ("F5", "G4"): 100,
    ("F6", "G3"): 85, ("F6", "G4"): 90,
}
REMOTE_SCORE = 30   # リモートスポット利用時の満足度(低い)


def build_model():
    model = Model("Airport_Gate_Assignment")

    pairs = [(f, g) for f in FLIGHTS for g in GATES
             if not (WIDE_BODY[f] and g not in WIDE_GATES)]
    x = {(f, g): model.addVar(vtype="B", name=f"x_{f}_{g}") for (f, g) in pairs}
    remote = {f: model.addVar(vtype="B", name=f"remote_{f}") for f in FLIGHTS}

    for f in FLIGHTS:
        model.addCons(
            quicksum(x[f, g] for g in GATES if (f, g) in x) + remote[f] == 1,
            f"assign_{f}")

    for g in GATES:
        for s in set(SLOT.values()):
            flights_in_slot = [f for f in FLIGHTS if SLOT[f] == s and (f, g) in x]
            if flights_in_slot:
                model.addCons(quicksum(x[f, g] for f in flights_in_slot) <= 1,
                               f"gate_exclusive_{g}_{s}")

    score = quicksum(SATISFACTION.get((f, g), 0) * x[f, g] for (f, g) in pairs)
    score += quicksum(REMOTE_SCORE * remote[f] for f in FLIGHTS)
    model.setObjective(score, "maximize")
    model.data = {"x": x, "remote": remote}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Satisfaction Value:", m.getObjVal())
