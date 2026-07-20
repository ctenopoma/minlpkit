"""フレキシブルジョブショップスケジューリング (Flexible Job Shop).

生産管理者が、複数のジョブ(受注ロット)を複数の工程(オペレーション)からなる
経路として、代替可能な機械群のいずれかに割り当てて完了時刻を最小化する
生産スケジューリング問題である。各オペレーションはどの機械でも処理できるわけではなく、
機械ごとに段取り・専用治具の有無で処理時間が異なる(=機械選択が処理時間を左右する)。
同一機械上で複数オペレーションが重複実行できない(離接制約)ため、機械選択(整数)と
オペレーション間の前後関係(整数)を同時に決める必要があり、単純な割当だけでは
実行不可能なスケジュールになりうる。

scale ノブ:
    small   : ジョブ2 × 工程2 × 機械2 (テスト用)
    default : ジョブ3 × 工程3 × 機械3
    large   : ジョブ4 × 工程3 × 機械4
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_job=2, n_op=2, n_mach=2),
    "default": dict(n_job=3, n_op=3, n_mach=3),
    "large":   dict(n_job=4, n_op=3, n_mach=4),
}

BIG_M = 1000.0


def _data(scale: str):
    cfg = SCALES[scale]
    nJ, nOp, nM = cfg["n_job"], cfg["n_op"], cfg["n_mach"]
    rng = np.random.default_rng(20260724 + nJ * 13 + nOp * 5 + nM * 3)
    # proc[j, o, m]: ジョブjの工程oを機械mで処理する所要時間(機械により差)
    proc = rng.uniform(3.0, 12.0, size=(nJ, nOp, nM))
    return dict(nJ=nJ, nOp=nOp, nM=nM, proc=proc)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nJ, nOp, nM, proc = d["nJ"], d["nOp"], d["nM"], d["proc"]

    model = Model("Flexible_Job_Shop")
    J, O, M = range(nJ), range(nOp), range(nM)

    # 機械選択(工程ごとに1台選ぶ)
    x = {(j, o, m): model.addVar(vtype="B", name=f"x_{j}_{o}_{m}") for j in J for o in O for m in M}
    # 実効処理時間・開始/終了時刻
    dur = {(j, o): model.addVar(vtype="C", lb=0.0, name=f"dur_{j}_{o}") for j in J for o in O}
    start = {(j, o): model.addVar(vtype="C", lb=0.0, name=f"start_{j}_{o}") for j in J for o in O}
    end = {(j, o): model.addVar(vtype="C", lb=0.0, name=f"end_{j}_{o}") for j in J for o in O}
    cmax = model.addVar(vtype="C", lb=0.0, name="cmax")

    for j in J:
        for o in O:
            model.addCons(quicksum(x[j, o, m] for m in M) == 1, name=f"assign_{j}_{o}")
            model.addCons(
                dur[j, o] == quicksum(x[j, o, m] * float(proc[j, o, m]) for m in M),
                name=f"dur_def_{j}_{o}")
            model.addCons(end[j, o] == start[j, o] + dur[j, o], name=f"end_def_{j}_{o}")
            if o > 0:
                # 工程は順序通り(前工程が終わってから次工程を開始)
                model.addCons(start[j, o] >= end[j, o - 1], name=f"precedence_{j}_{o}")
            model.addCons(end[j, o] <= cmax, name=f"makespan_{j}_{o}")

    # 同一機械上のオペレーションは重複不可(離接制約、順序は補助バイナリで決める)
    for m in M:
        ops_on_m = [(j, o) for j in J for o in O]
        for idx1 in range(len(ops_on_m)):
            for idx2 in range(idx1 + 1, len(ops_on_m)):
                j1, o1 = ops_on_m[idx1]
                j2, o2 = ops_on_m[idx2]
                y = model.addVar(vtype="B", name=f"seq_{m}_{j1}_{o1}_{j2}_{o2}")
                both_on_m = model.addVar(vtype="B", name=f"both_{m}_{j1}_{o1}_{j2}_{o2}")
                model.addCons(both_on_m <= x[j1, o1, m], name=f"both_lb1_{m}_{j1}_{o1}_{j2}_{o2}")
                model.addCons(both_on_m <= x[j2, o2, m], name=f"both_lb2_{m}_{j1}_{o1}_{j2}_{o2}")
                model.addCons(both_on_m >= x[j1, o1, m] + x[j2, o2, m] - 1,
                              name=f"both_lb3_{m}_{j1}_{o1}_{j2}_{o2}")
                model.addCons(
                    start[j2, o2] >= end[j1, o1] - BIG_M * (1 - y) - BIG_M * (1 - both_on_m),
                    name=f"noover1_{m}_{j1}_{o1}_{j2}_{o2}")
                model.addCons(
                    start[j1, o1] >= end[j2, o2] - BIG_M * y - BIG_M * (1 - both_on_m),
                    name=f"noover2_{m}_{j1}_{o1}_{j2}_{o2}")

    model.setObjective(cmax, "minimize")
    model.data = {"x": x, "start": start, "end": end, "cmax": cmax,
                  "scale": scale, "dims": (nJ, nOp, nM)}
    return model


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Makespan:", m.getObjVal())


if __name__ == "__main__":
    main()
