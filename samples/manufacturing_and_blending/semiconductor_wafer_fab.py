"""半導体ウェハ工場搬送スケジュール (Semiconductor Wafer Fab Routing)

事業ストーリー
--------------
半導体製造ラインの「搬送システム管理者」が、ウェハキャリア(ロット)を各工程間で運ぶ
自動搬送ロボット(OHT/AMR)への割当を決める意思決定である。各ロットはいずれか1台の
ロボットに割り当てなければならず、ロボットには同時搬送できるキャリア数の上限(積載容量)
がある。ロボットごとに現在位置からロットの搬送元までの移動時間が異なるため、割当次第で
搬送完了までの総所要時間が変わる。さらに一部のロットは高優先度(歩留まりに影響する
工程間搬送)であり、優先ロットは搬送開始までの待ち時間に上限が課される。管理者は、
容量制約と優先ロットの納期制約を満たしながら、総搬送時間を最小化するロボット割当を
決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_wafer=6, n_robot=3),
    "default": dict(n_wafer=10, n_robot=4),
    "large": dict(n_wafer=16, n_robot=5),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_wafer, n_robot = cfg["n_wafer"], cfg["n_robot"]
    wafers, robots = range(n_wafer), range(n_robot)

    # ロボット r がロット w を搬送する所要時間(位置関係で変動)
    transit_time = {(w, r): 5 + ((w * 3 + r * 7) % 12) for w in wafers for r in robots}
    is_priority = {w: 1 if w % 4 == 0 else 0 for w in wafers}
    robot_capacity = 3  # ロボット1台が同時に担当できるロット数上限

    model = Model("Semiconductor_Wafer_Fab")

    assign = {(w, r): model.addVar(vtype="B", name=f"as_{w}_{r}") for w in wafers for r in robots}

    for w in wafers:
        model.addCons(quicksum(assign[w, r] for r in robots) == 1, name=f"wafer_{w}")
    for r in robots:
        model.addCons(quicksum(assign[w, r] for w in wafers) <= robot_capacity, name=f"robot_capacity_{r}")

    # 優先ロットは搬送時間が短いロボット(所要時間9以下)にのみ割当可能(納期厳守)
    for w in wafers:
        if is_priority[w]:
            for r in robots:
                if transit_time[w, r] > 9:
                    model.addCons(assign[w, r] == 0, name=f"priority_limit_{w}_{r}")

    model.setObjective(
        quicksum(assign[w, r] * transit_time[w, r] for w in wafers for r in robots), "minimize")
    model.data = {"assign": assign, "dims": (n_wafer, n_robot)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Routing Time:", m.getObjVal())
