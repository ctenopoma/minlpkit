"""恒等並列機械へのジョブ割当 (MILP, 強い対称性を持つ)

対称性検出・対称性除去の題材。機械が恒等なので任意の2機械を
入れ替えても同じ解 = 機械添字の置換対称性(M!個)を持つ。

    min  Cmax
    s.t. Σ_m x[j,m] = 1              (各ジョブは1機械 / assign_j)
         Σ_j p_j x[j,m] <= Cmax      (機械負荷 / makespan_m)  ※全機械で同形

symmetry_break=True で辞書式順序制約(機械負荷を非増加に固定)を追加し、
恒等機械の置換対称性を除去する。恒等機械なのでこの制約はWLOGで有効(最適値を保つ)。
"""

from __future__ import annotations

from pyscipopt import Model, quicksum

# 対称性が効く程度に大きめ(13ジョブ)。等処理時間ジョブも含み対称性を強める。
JOBS = {f"J{i+1}": p for i, p in enumerate(
    [3, 5, 2, 4, 6, 3, 5, 2, 4, 6, 3, 5, 7])}
N_MACHINES = 4  # 恒等機械


def build_model(symmetry_break: bool = False) -> Model:
    m = Model("parallel_machines")
    machines = [f"M{k+1}" for k in range(N_MACHINES)]
    x = {(j, mc): m.addVar(vtype="B", name=f"x_{j}_{mc}") for j in JOBS for mc in machines}
    cmax = m.addVar(lb=0, name="cmax")

    for j in JOBS:
        m.addCons(quicksum(x[j, mc] for mc in machines) == 1, name=f"assign_{j}")

    load = {mc: quicksum(JOBS[j] * x[j, mc] for j in JOBS) for mc in machines}
    for mc in machines:
        m.addCons(load[mc] <= cmax, name=f"makespan_{mc}")

    if symmetry_break:
        # 機械負荷を非増加に: load_M1 >= load_M2 >= ... (恒等機械なのでWLOG有効)
        for a, b in zip(machines, machines[1:]):
            m.addCons(load[a] >= load[b], name=f"symbreak_{a}_{b}")

    m.setObjective(cmax, "minimize")
    m.data = dict(x=x, cmax=cmax, machines=machines)
    return m


def main() -> None:
    for sb in (False, True):
        m = build_model(symmetry_break=sb)
        m.hideOutput()
        m.setParam("limits/time", 60)
        m.optimize()
        print(f"symmetry_break={sb}: status={m.getStatus()} makespan={m.getObjVal():.0f} "
              f"nodes={m.getNNodes()} time={m.getSolvingTime():.2f}s")


if __name__ == "__main__":
    main()
