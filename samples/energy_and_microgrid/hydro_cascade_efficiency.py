"""水頭依存効率を持つ多段ダム放流計画 (Hydro Cascade with Head-Dependent Efficiency).

事業ストーリー
--------------
一級河川に連なる複数ダムを一括運用する電力会社の「水系運用担当者」が、季節(数十〜
百数十日)にわたる各ダムの放流量を決める意思決定である。上流ダムの放流は下流ダムへの
流入となり(河川流下の時間遅れを伴う)、各ダムの発電量は「放流量 × 水頭(貯水位に依存)」
という**双線形**で決まる。加えて灌漑用水の取水下限があり、発電に有利なタイミングと
灌漑が必要なタイミングが一致するとは限らない。

各制約の業務的意味:
- **発電量 = 放流量 × 水頭(双線形)**: 水力発電のタービン出力は概ね
  P = k・q・h(q=放流量、h=有効落差)に比例する。落差 h は貯水位(=貯水量)の関数であり、
  貯水位が高いほど同じ放流量でも発電量が大きい。この「いつ貯めて、いつ放つか」が
  発電価値を左右する非凸構造そのもの(近似ではなく水力発電の物理)。
- **貯水量バランス(時間結合)**: 各期の貯水量は前期の貯水量 + 自流域流入 + 上流からの
  放流・越流(1期の河川流下遅れ付き) − 自ダム放流 − 越流。上流の意思決定が下流の
  制約を通じて全期間に波及する。
- **越流(スピル)**: タービン通水能力を超える水は発電に使えず越流させる必要がある
  (physical capacity)。
- **灌漑取水下限**: 指定ダムは灌漑期に最低放流量を守る義務があり(農業用水の契約)、
  発電の都合だけで放流量を決められない。
- **期末貯水量下限(渇水対策の備蓄目標)**: 計画期間の終わりに一定量以上を残すことが
  求められ、「今使うか、将来のために貯めるか」というトレードオフを生む。
- **火力バックストップ**: 系統全体の電力需要はハイドロ + 高コストの火力代替
  (Spot火力調達)で満たす。水力だけでは需要を満たせない期・満たしすぎる期があっても
  常に実行可能。

なぜ非凸が業務要件として自然に入るか:
水力発電の出力が「流量 × 落差」で決まることは近似ではなく物理そのものであり、
貯水位(=状態変数)が時間を通じて変化する以上、この積は本質的に双線形になる。
カスケード河川の流下遅れは在庫問題と同型の時間結合を追加し、灌漑下限は発電最適とは
独立した外生制約として双線形の実行可能領域を非対称に縛る。

scale ノブ(硬さの源泉: 物理結合(放流×水頭の双線形) + 時間結合(カスケード流下遅れ・
貯水量の期跨ぎ)):
    small   : ダム3 × 期14   (テスト・ハンズオン用。数分で最適)
    default : ダム6 × 期90   (診断の題材。30秒でgap残存)
    large   : ダム8 × 期180
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_dam=2, n_period=8,   demand_factor=0.40),
    "default": dict(n_dam=5, n_period=22,  demand_factor=0.72),
    "large":   dict(n_dam=8, n_period=180, demand_factor=0.72),
}

THERMAL_COST = 140.0   # 火力バックストップ単価[$/MWh](水力より十分高い)


def _data(scale: str):
    cfg = SCALES[scale]
    nD, nT, demand_factor = cfg["n_dam"], cfg["n_period"], cfg["demand_factor"]
    rng = np.random.default_rng(20260722 + nD * 53 + nT)

    # ダム諸元(上流=0 -> 下流=nD-1のカスケード)
    smin = np.round(rng.uniform(30, 60, nD), 1)
    smax = np.round(smin + rng.uniform(120, 260, nD), 1)
    s0 = np.round(smin + 0.55 * (smax - smin), 1)          # 初期貯水量
    qmax = np.round(rng.uniform(18, 40, nD), 1)             # タービン通水能力上限
    # 水頭: head = h0 + alpha*貯水量 (局所線形近似。貯水位-水頭曲線の代表区間)
    h0 = np.round(rng.uniform(8, 20, nD), 2)
    alpha = np.round(rng.uniform(0.35, 0.7, nD), 3)
    k_gen = np.round(rng.uniform(0.070, 0.095, nD), 4)      # 発電係数(MW / (m^3/s * m))

    # 自流域流入(季節パターン: 融雪期に高く、その後逓減)+ 下流ほど流域面積が広く流入増
    tt = np.arange(nT)
    season = 1.0 + 0.9 * np.exp(-((tt - nT * 0.28) ** 2) / (2 * (nT * 0.16) ** 2))
    base_local = rng.uniform(3.0, 6.0, nD) * (1.0 + 0.5 * np.arange(nD))
    local_inflow = np.outer(base_local, season) * (1.0 + rng.uniform(-0.05, 0.05, (nD, nT)))
    local_inflow = np.maximum(local_inflow, 1.0)

    # 灌漑取水下限(下流の農業用水期=灌漑シーズンのみ、下流1-2ダムに適用)
    irrig_min = np.zeros((nD, nT))
    irrig_season = (tt >= nT * 0.30) & (tt <= nT * 0.70)
    for d in range(max(1, nD - 2), nD):
        irrig_min[d, irrig_season] = rng.uniform(9.0, 14.0)

    # 期末貯水量目標(渇水対策の備蓄)
    s_target = np.round(smin + 0.35 * (smax - smin), 1)

    # 系統電力需要(山谷) — 水力+火力で満たす
    daily = 1.0 + 0.30 * np.sin(2 * np.pi * tt / max(nT, 2) * 3.0)
    base_dem = float((k_gen * qmax * (h0 + alpha * smax)).sum()) * demand_factor
    demand = np.maximum(base_dem * daily * (1.0 + rng.uniform(-0.04, 0.04, nT)), 5.0)

    return dict(nD=nD, nT=nT, smin=smin, smax=smax, s0=s0, qmax=qmax, h0=h0,
                alpha=alpha, k_gen=k_gen, local_inflow=local_inflow,
                irrig_min=irrig_min, s_target=s_target, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nD, nT = d["nD"], d["nT"]
    smin, smax, s0, qmax = d["smin"], d["smax"], d["s0"], d["qmax"]
    h0, alpha, k_gen = d["h0"], d["alpha"], d["k_gen"]
    local_inflow, irrig_min, s_target, demand = (
        d["local_inflow"], d["irrig_min"], d["s_target"], d["demand"])

    m = Model("Hydro_Cascade_Efficiency")
    D, T = range(nD), range(nT)

    S = {(dd, t): m.addVar(vtype="C", lb=float(smin[dd]), ub=float(smax[dd]), name=f"S_{dd}_{t}")
         for dd in D for t in T}
    q = {(dd, t): m.addVar(vtype="C", lb=0.0, ub=float(qmax[dd]), name=f"q_{dd}_{t}")
         for dd in D for t in T}
    sp = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"sp_{dd}_{t}") for dd in D for t in T}
    head = {(dd, t): m.addVar(vtype="C",
                              lb=float(h0[dd] + alpha[dd] * smin[dd]),
                              ub=float(h0[dd] + alpha[dd] * smax[dd]),
                              name=f"head_{dd}_{t}") for dd in D for t in T}
    gen = {(dd, t): m.addVar(vtype="C", lb=0.0, name=f"gen_{dd}_{t}") for dd in D for t in T}
    thermal = {t: m.addVar(vtype="C", lb=0.0, name=f"thermal_{t}") for t in T}

    for dd in D:
        for t in T:
            # 水頭の定義(貯水量の線形関数)
            m.addCons(head[dd, t] == float(h0[dd]) + float(alpha[dd]) * S[dd, t],
                      name=f"head_def_{dd}_{t}")
            # 発電量 = 発電係数 * 放流量 * 水頭 (双線形)
            m.addCons(gen[dd, t] == float(k_gen[dd]) * q[dd, t] * head[dd, t],
                      name=f"gen_def_{dd}_{t}")
            # 灌漑取水下限
            if irrig_min[dd, t] > 0:
                m.addCons(q[dd, t] >= float(irrig_min[dd, t]), name=f"irrig_{dd}_{t}")

            prev = S[dd, t - 1] if t > 0 else float(s0[dd])
            # 上流(dd-1)からの放流・越流は1期遅れで自流域流入に加算される(河川流下時間)
            if dd == 0 or t == 0:
                upstream_in = 0.0
            else:
                upstream_in = q[dd - 1, t - 1] + sp[dd - 1, t - 1]
            m.addCons(
                S[dd, t] == prev + float(local_inflow[dd, t]) + upstream_in - q[dd, t] - sp[dd, t],
                name=f"storage_balance_{dd}_{t}")

        # 期末貯水量下限(渇水対策の備蓄目標)
        m.addCons(S[dd, nT - 1] >= float(s_target[dd]), name=f"terminal_storage_{dd}")

    for t in T:
        m.addCons(quicksum(gen[dd, t] for dd in D) + thermal[t] >= float(demand[t]),
                  name=f"power_balance_{t}")

    obj = quicksum(THERMAL_COST * thermal[t] for t in T)
    m.setObjective(obj, "minimize")

    m.data = dict(S=S, q=q, gen=gen, thermal=thermal, scale=scale, dims=(nD, nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
