"""バッチスケジューリング (MINLP)

ジョブごとにバッチ数(整数)×バッチサイズ(連続)を決め、マシンに割り当てる。
- n_j · s_j >= d_j            : 双線形(整数×連続)
- バッチ処理時間 = setup + k·s^0.6 : 凹べき乗(規模の経済) → 非凸
- マシン負荷 = Σ x_jm · T_j     : バイナリ×連続の双線形
目的はメイクスパン最小化。

実行: uv run python samples/scheduling.py
"""

from pyscipopt import Model, quicksum

# ---- データ ----
# demand: 必要生産量, setup: バッチあたり段取り時間, k: 処理時間係数
JOBS = {
    "J1": dict(demand=120, setup=2.0, k=1.5),
    "J2": dict(demand=200, setup=1.5, k=1.2),
    "J3": dict(demand=80,  setup=3.0, k=2.0),
    "J4": dict(demand=150, setup=1.0, k=1.8),
    "J5": dict(demand=250, setup=2.5, k=1.0),
    "J6": dict(demand=100, setup=1.5, k=1.6),
}
MACHINES = {"M1": dict(speed=1.0), "M2": dict(speed=0.8)}  # speed: 処理時間倍率(小=速い)
N_MAX = 8       # 最大バッチ数
S_MIN, S_MAX = 5.0, 60.0  # バッチサイズ範囲


def build_model(linearize_ns: bool = False) -> Model:
    """linearize_ns=True で n·s を汎用ヘルパー linearize_product で厳密線形化する。"""
    m = Model("batch_scheduling")

    x, n, s, T = {}, {}, {}, {}
    for j in JOBS:
        n[j] = m.addVar(vtype="I", lb=1, ub=N_MAX, name=f"n_{j}")
        s[j] = m.addVar(lb=S_MIN, ub=S_MAX, name=f"s_{j}")
        T[j] = m.addVar(lb=0, name=f"T_{j}")
        for mc in MACHINES:
            x[j, mc] = m.addVar(vtype="B", name=f"x_{j}_{mc}")

    cmax = m.addVar(lb=0, name="cmax")

    # n·s を汎用ヘルパーで厳密線形化(scheduling_plant と同じ linearize_product を再利用)
    ns = {}
    if linearize_ns:
        from minlpkit.transforms import linearize_product
        for j in JOBS:
            ns[j] = linearize_product(m, n[j], s[j], 1, N_MAX, S_MIN, S_MAX, f"ns_{j}")
    else:
        for j in JOBS:
            ns[j] = n[j] * s[j]

    for j, d in JOBS.items():
        # 総生産量が需要を満たす (双線形 or 線形化後)
        m.addCons(ns[j] >= d["demand"])
        # ジョブ総処理時間 (凹べき乗を含む非凸等式)
        m.addCons(T[j] == n[j] * (d["setup"] + d["k"] * s[j] ** 0.6))
        # ちょうど1台に割当
        m.addCons(quicksum(x[j, mc] for mc in MACHINES) == 1)

    for mc, md in MACHINES.items():
        # マシン負荷 (バイナリ×連続の双線形) がメイクスパン以下
        m.addCons(quicksum(x[j, mc] * T[j] for j in JOBS) * md["speed"] <= cmax)

    m.setObjective(cmax, "minimize")
    m.data = dict(x=x, n=n, s=s, T=T, cmax=cmax)
    return m


def main() -> None:
    m = build_model()
    m.setParam("limits/time", 120)
    m.setParam("limits/gap", 0.01)
    m.optimize()

    print(f"\nstatus={m.getStatus()}  makespan={m.getObjVal():.2f}  gap={m.getGap() * 100:.2f}%  "
          f"nodes={m.getNNodes()}  time={m.getSolvingTime():.1f}s")
    x, n, s, T = m.data["x"], m.data["n"], m.data["s"], m.data["T"]
    for mc in MACHINES:
        jobs = [j for j in JOBS if m.getVal(x[j, mc]) > 0.5]
        load = sum(m.getVal(T[j]) for j in jobs) * MACHINES[mc]["speed"]
        print(f"\n{mc} (負荷 {load:.1f}):")
        for j in jobs:
            print(f"  {j}: バッチ {m.getVal(n[j]):.0f} × サイズ {m.getVal(s[j]):.1f} "
                  f"(生産 {m.getVal(n[j]) * m.getVal(s[j]):.0f} / 需要 {JOBS[j]['demand']}, "
                  f"処理時間 {m.getVal(T[j]):.1f})")


if __name__ == "__main__":
    main()
