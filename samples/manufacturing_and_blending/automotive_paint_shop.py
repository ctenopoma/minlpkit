"""自動車塗装順序・段取り最適化 (Automotive Paint Shop Sequencing)

事業ストーリー
--------------
自動車組立工場の塗装工程管理者が、当直の生産スケジュール(タイムスロットごとにどの色を
塗るか)を決める。同じ色を連続して流せば色替え(パージ・洗浄)が不要だが、色替えのたびに
段取り時間とロス塗料のコストが発生するため、需要を満たしつつ色替え回数を最小化したい。

各制約の業務的意味:
- **各タイムスロットで生産する色は1色のみ**: 塗装ブースは同時に1色しか流せない
  (物理的な排他制約)。
- **色ごとの需要充足**: 各色について、生産量(スロット数×スロット当たり生産台数)が
  その日の需要台数以上でなければならない。
- **色替え検知(二値変数)**: 直前スロットと異なる色を生産し始めたスロットでは
  色替えフラグが立ち、段取りコストが発生する。これは典型的な「立ち上がり(startup)」
  型の制約で、生産計画・ユニットコミットメントと同じ構造を持つ。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

COLORS = ["white", "black", "red"]
N_SLOTS = 6
SLOT_OUTPUT = 12          # 1スロットあたりの生産可能台数
DEMAND = {"white": 25, "black": 20, "red": 10}
CHANGEOVER_COST = 50


def build_model():
    model = Model("Automotive_Paint_Shop")

    y = {(k, t): model.addVar(vtype="B", name=f"y_{k}_{t}")
         for k in COLORS for t in range(N_SLOTS)}
    change = {t: model.addVar(vtype="B", name=f"ch_{t}") for t in range(1, N_SLOTS)}

    for t in range(N_SLOTS):
        model.addCons(quicksum(y[k, t] for k in COLORS) == 1, f"one_color_{t}")

    for k in COLORS:
        model.addCons(
            SLOT_OUTPUT * quicksum(y[k, t] for t in range(N_SLOTS)) >= DEMAND[k],
            f"demand_{k}")

    for t in range(1, N_SLOTS):
        for k in COLORS:
            model.addCons(change[t] >= y[k, t] - y[k, t - 1], f"changeover_{k}_{t}")

    model.setObjective(CHANGEOVER_COST * quicksum(change[t] for t in range(1, N_SLOTS)),
                        "minimize")
    model.data = {"y": y, "change": change}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Change Cost:", m.getObjVal())
