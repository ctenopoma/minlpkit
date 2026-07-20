"""鉄鋼連続鋳造製造スケジュール (Steel Continuous Casting Scheduling)

事業ストーリー
--------------
製鉄所の「鋳造工程スケジューラ」が、複数の鋳造ライン(ストランド)上で連続鋳造される
複数のヒート(溶鋼バッチ)の投入順序と開始時刻を決める意思決定である。連続鋳造は
タンディッシュ(中間容器)を空にできないため、同一ラインの連続するヒート間には
最小・最大の投入間隔(鋳造ギャップ)が業務上定められている(間隔が短すぎると凝固が
追いつかず、長すぎるとタンディッシュ内の溶鋼が冷えて品質不良になる)。また各ヒートは
いずれか1本のラインに割り当てる必要があり、鋼種が変わるとライン切替に段取り時間が
かかる。スケジューラは、ライン容量とギャップ制約を満たしながら、全ヒートの鋳造完了
までの総所要時間(メイクスパン)を最小化する順序・ライン割当を決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_heat=4, n_line=2),
    "default": dict(n_heat=6, n_line=2),
    "large": dict(n_heat=9, n_line=3),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_heat, n_line = cfg["n_heat"], cfg["n_line"]
    heats, lines = range(n_heat), range(n_line)

    gap_min, gap_max = 45.0, 55.0  # 同一ライン上の連続ヒート間の最小・最大鋳造ギャップ [分]
    grade_change_setup = 15.0  # 鋼種切替時の段取り時間 [分]
    is_grade_change = {h: 1 if h % 3 == 0 else 0 for h in heats}  # 前工程からの鋼種変更フラグ
    big_m = 2000.0

    model = Model("Steel_Continuous_Casting")

    start = {h: model.addVar(vtype="C", lb=0, name=f"start_{h}") for h in heats}
    assign = {(h, l): model.addVar(vtype="B", name=f"assign_{h}_{l}") for h in heats for l in lines}
    # 順序変数: 同一ラインに割り当てられたヒート対 (h1, h2) で h1 が先行するか
    order = {(h1, h2): model.addVar(vtype="B", name=f"order_{h1}_{h2}")
             for h1 in heats for h2 in heats if h1 < h2}
    makespan = model.addVar(vtype="C", lb=0, name="makespan")

    for h in heats:
        model.addCons(quicksum(assign[h, l] for l in lines) == 1, name=f"heat_line_{h}")

    for h1 in heats:
        for h2 in heats:
            if h1 >= h2:
                continue
            for l in lines:
                # 同一ラインに割り当てられた場合のみ、順序に応じたギャップ制約を課す(disjunctive)
                setup = grade_change_setup if is_grade_change[h2] else 0.0
                same_line = assign[h1, l] + assign[h2, l] - 1  # 両方 l に割当なら1、それ以外は<=0
                model.addCons(
                    start[h2] - start[h1] >= gap_min + setup - big_m * (1 - order[h1, h2]) - big_m * (1 - same_line),
                    name=f"gap_min_{h1}_{h2}_{l}")
                model.addCons(
                    start[h2] - start[h1] <= gap_max + big_m * (1 - order[h1, h2]) + big_m * (1 - same_line),
                    name=f"gap_max_{h1}_{h2}_{l}")
                model.addCons(
                    start[h1] - start[h2] >= gap_min - big_m * order[h1, h2] - big_m * (1 - same_line),
                    name=f"gap_min_rev_{h1}_{h2}_{l}")

    for h in heats:
        model.addCons(makespan >= start[h], name=f"makespan_{h}")

    model.setObjective(makespan, "minimize")
    model.data = {"start": start, "assign": assign, "makespan": makespan, "dims": (n_heat, n_line)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("EndTime:", m.getObjVal())
