"""バッチ反応器スケジューリング + プラント物理モデル (MINLP)

scheduling.py の拡張版。バッチ処理を「反応器の物理挙動」で置き換え、
制約式自体の複雑さ(非線形の種類)を増やしたモデル。

各ジョブ(製品)ごとに決めるもの:
  - 割当マシン x[j,m] (バイナリ)、バッチ数 n_j (整数)、バッチサイズ s_j (連続)
  - 反応温度 T_j (連続)、反応時間 tau_j (連続)

物理モデル(非線形制約の内訳):
  - Arrhenius式:    k_j = A·exp(−Ea/(R·T_j))          … exp(1/T) 型の非凸
  - 転化率:         X_j = 1 − exp(−k_j·tau_j)          … ネストしたexp + 双線形
  - 需要充足:       n_j·s_j·X_j ≥ d_j                  … 三重積
  - 昇温時間:       heat_j = s_j·(T_j−T0)/P_heat       … 双線形
  - エネルギー:     e_j = n_j·s_j·(T_j−T0)             … 三重積(目的関数に効く)
  - 除熱能力:       ΔH·s_j·X_j ≤ Qmax_m·tau_j (割当時) … 有理式相当の三重積
  - マシン耐熱:     T_j ≤ Σ x[j,m]·Tmax_m

実行: uv run python samples/scheduling_plant.py
"""

from pyscipopt import Model, exp, quicksum

# ---- データ ----
# demand: 必要生産量[t], setup: 段取り[h], dH: 反応熱係数
JOBS = {
    "J1": dict(demand=120, setup=2.0, dH=8.0),
    "J2": dict(demand=200, setup=1.5, dH=5.0),
    "J3": dict(demand=80,  setup=3.0, dH=12.0),
    "J4": dict(demand=150, setup=1.0, dH=6.0),
    "J5": dict(demand=250, setup=2.5, dH=4.0),
    "J6": dict(demand=100, setup=1.5, dH=10.0),
}
# speed: 処理時間倍率, tmax: 耐熱温度[K], qmax: 除熱能力
MACHINES = {
    "M1": dict(speed=1.0, tmax=380.0, qmax=900.0),
    "M2": dict(speed=0.8, tmax=355.0, qmax=1400.0),
}

N_MAX = 8
S_MIN, S_MAX = 5.0, 60.0     # バッチサイズ[t]
T_MIN, T_MAX = 320.0, 380.0  # 反応温度[K]
TAU_MIN, TAU_MAX = 0.5, 16.0 # 反応時間[h]
T0 = 300.0                   # 初期温度[K]
ARRH_A = 5.0e8               # 頻度因子[1/h]
EA_R = 7000.0                # Ea/R [K]  → k(320K)=0.16, k(380K)=4.9 [1/h]
X_REQ = 0.90                 # 要求転化率
P_HEAT = 400.0               # 昇温能力 → heat = s·(T−T0)/P_HEAT [h]
ENERGY_COST = 0.004          # エネルギー項の目的関数重み

import math

K_LB = ARRH_A * math.exp(-EA_R / T_MIN)
K_UB = ARRH_A * math.exp(-EA_R / T_MAX)


def build_model(linearize_ns: bool = False) -> Model:
    """linearize_ns=True で n·s を整数×連続の厳密線形化(分解)に置換する。

    n は整数なので、指示変数 δ_v(n=v)と s の分解 s=Σ_v s_v(s_v は n=v のとき有効)で
    ns = Σ_v v·s_v が n·s を厳密に表す(McCormick緩和のギャップを消す)。
    これで demand/energy の三重積が ns·X, ns·(T−T0) の双線形に落ちる。
    """
    m = Model("batch_reactor_scheduling")

    x, n, s, T, tau, k, X, tb, tt, e = {}, {}, {}, {}, {}, {}, {}, {}, {}, {}
    for j in JOBS:
        n[j] = m.addVar(vtype="I", lb=1, ub=N_MAX, name=f"n_{j}")
        s[j] = m.addVar(lb=S_MIN, ub=S_MAX, name=f"s_{j}")
        T[j] = m.addVar(lb=T_MIN, ub=T_MAX, name=f"T_{j}")
        tau[j] = m.addVar(lb=TAU_MIN, ub=TAU_MAX, name=f"tau_{j}")
        k[j] = m.addVar(lb=K_LB, ub=K_UB, name=f"k_{j}")          # 反応速度定数
        X[j] = m.addVar(lb=X_REQ, ub=0.999, name=f"X_{j}")        # 転化率
        tb[j] = m.addVar(lb=0, name=f"tb_{j}")                    # 1バッチ時間
        tt[j] = m.addVar(lb=0, name=f"tt_{j}")                    # ジョブ総時間
        e[j] = m.addVar(lb=0, name=f"e_{j}")                      # エネルギー
        for mc in MACHINES:
            x[j, mc] = m.addVar(vtype="B", name=f"x_{j}_{mc}")

    cmax = m.addVar(lb=0, name="cmax")

    # n·s の厳密線形化。汎用ヘルパー minlpkit.transforms.linearize_product を使う(横展開)
    ns_expr = {}
    if linearize_ns:
        from minlpkit.transforms import linearize_product
        for j in JOBS:
            ns_expr[j] = linearize_product(m, n[j], s[j], 1, N_MAX, S_MIN, S_MAX, f"ns_{j}")
    else:
        for j in JOBS:
            ns_expr[j] = n[j] * s[j]  # 双線形(SCIPはMcCormickで緩和)

    for j, d in JOBS.items():
        # --- 反応速度論 ---
        m.addCons(k[j] == ARRH_A * exp(-EA_R / T[j]), name=f"arrhenius_{j}")
        m.addCons(X[j] == 1 - exp(-k[j] * tau[j]), name=f"conversion_{j}")
        # --- 需要充足 (有効生産量 = n·s·X) ---
        m.addCons(ns_expr[j] * X[j] >= d["demand"], name=f"demand_{j}")
        # --- 時間構造: 1バッチ = 段取り + 昇温 + 反応 ---
        m.addCons(tb[j] == d["setup"] + s[j] * (T[j] - T0) / P_HEAT + tau[j], name=f"batchtime_{j}")
        m.addCons(tt[j] == n[j] * tb[j], name=f"jobtime_{j}")
        # --- エネルギー消費 ---
        m.addCons(e[j] == ns_expr[j] * (T[j] - T0), name=f"energy_{j}")
        # --- 割当と機械依存の制限 ---
        m.addCons(quicksum(x[j, mc] for mc in MACHINES) == 1, name=f"assign_{j}")
        m.addCons(T[j] <= quicksum(x[j, mc] * MACHINES[mc]["tmax"] for mc in MACHINES), name=f"tmax_{j}")
        # 平均発熱率 dH·s·X/tau が割当先の除熱能力以下
        m.addCons(
            d["dH"] * s[j] * X[j] <= quicksum(x[j, mc] * MACHINES[mc]["qmax"] for mc in MACHINES) * tau[j],
            name=f"cooling_{j}",
        )

    for mc, md in MACHINES.items():
        m.addCons(quicksum(x[j, mc] * tt[j] for j in JOBS) * md["speed"] <= cmax, name=f"load_{mc}")

    m.setObjective(cmax + ENERGY_COST * quicksum(e[j] for j in JOBS), "minimize")
    m.data = dict(x=x, n=n, s=s, T=T, tau=tau, k=k, X=X, tb=tb, tt=tt, e=e, cmax=cmax)
    return m


def main() -> None:
    m = build_model()
    m.setParam("limits/time", 300)
    m.setParam("limits/gap", 0.02)
    m.optimize()

    print(f"\nstatus={m.getStatus()}  obj={m.getObjVal():.2f}  gap={m.getGap() * 100:.2f}%  "
          f"nodes={m.getNNodes()}  time={m.getSolvingTime():.1f}s")
    d = m.data
    cmax_v = m.getVal(d["cmax"])
    energy = sum(m.getVal(d["e"][j]) for j in JOBS)
    print(f"メイクスパン={cmax_v:.1f}h  総エネルギー={energy:,.0f}  (目的値 = cmax + {ENERGY_COST}×energy)")
    for mc in MACHINES:
        jobs = [j for j in JOBS if m.getVal(d["x"][j, mc]) > 0.5]
        load = sum(m.getVal(d["tt"][j]) for j in jobs) * MACHINES[mc]["speed"]
        print(f"\n{mc} (負荷 {load:.1f}h, 耐熱 {MACHINES[mc]['tmax']:.0f}K, 除熱 {MACHINES[mc]['qmax']:.0f}):")
        for j in jobs:
            n_v, s_v = m.getVal(d["n"][j]), m.getVal(d["s"][j])
            T_v, tau_v = m.getVal(d["T"][j]), m.getVal(d["tau"][j])
            X_v, tb_v = m.getVal(d["X"][j]), m.getVal(d["tb"][j])
            qrate = JOBS[j]["dH"] * s_v * X_v / tau_v
            print(f"  {j}: {n_v:.0f}バッチ×{s_v:.1f}t  T={T_v:.1f}K  反応{tau_v:.1f}h  "
                  f"転化率{X_v * 100:.1f}%  1バッチ{tb_v:.1f}h  "
                  f"有効生産{n_v * s_v * X_v:.0f}/{JOBS[j]['demand']}  発熱率{qrate:.0f}")


if __name__ == "__main__":
    main()
