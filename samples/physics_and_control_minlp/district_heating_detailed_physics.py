"""地域熱供給網 (District Heating Network) の詳細物理最適化モデル (MINLP)

事業ストーリー
--------------
地域熱供給事業者の「プラント運転員」が、熱源プラントから放射状(木構造)に広がる配管網を
通じて複数需要家へ熱を届けるための、各期(時間帯)ごとの質量流量・温度・熱源出力・
ポンプ動力を決める意思決定である。配管内の質量流量と温度のダイナミクス(エネルギー保存)、
圧力損失(Darcy-Weisbach簡易形)とポンプ動力、節点における流量と温度の混合(双線形)、
熱損失の温度依存性(双線形)を詳細にモデル化し、総ポンプ動力と燃料コストの合計を
最小化する。

各制約の業務的意味:
- **需要家の熱需要 = 消費流量 × 比熱 × (供給温度 − 還流温度)(双線形)**: 熱需要[kW]を
  満たすための消費流量は温度差に反比例するため、Q=m·cp·ΔT という積の等式制約になる。
- **配管の熱損失(双線形)**: 外気への熱損失は配管入口温度と外気温の差に比例するが、
  それを流量×温度降下のエネルギー収支として表すと m·cp·(T_in − T_out) = K·(T_in − T_env)
  という双線形の等式になる(流量が小さいほど同じ熱損失でも温度降下が大きい)。
- **節点での完全混合(双線形)**: 複数配管から流入した熱媒体はよく混合されるため、
  出口の節点温度は流量加重平均になる(Σ m_e·T_out_e = (Σ m_e)·T_node)。
- **圧力損失(流量の2乗、非凸)**: Darcy-Weisbach簡易形 dp = K·m² により、配管の圧力損失は
  流量の2乗に比例する。
- **ポンプ動力(双線形)**: 総ポンプ動力は各配管の質量流量×圧力損失の和に比例する
  (仕事率 = 流量×圧力損失)。
- **熱源温度のランプ制約(時間結合)**: ボイラーの出口温度は熱慣性のため期をまたいで
  急変できない(|T_source[t] − T_source[t-1]| ≤ ランプ上限)。これにより各期の最適化が
  独立に分解できなくなり、需要山谷全体を見渡した運転計画が必要になる。

なぜ非凸が業務要件として自然に入るか:
熱エネルギー Q=m·cp·ΔT、圧力損失∝流量²、節点混合の加重平均はいずれも熱水力の物理法則
そのものであり、近似的な線形代替では現実の運転計画にならない。熱源のランプ制約は
実プラントの熱慣性という物理的制約であり、期をまたぐ結合を生む。

scale ノブ(硬さの源泉: 物理結合(流量×温度の双線形が複数箇所) + 時間結合(熱源温度ランプ) +
現実規模(ノード数・期数)):
    small   : ノード4  × 期4    (テスト・ハンズオン用。数分で最適)
    default : ノード12 × 期12   (診断の題材。30秒でgap残存。既存センサスのweak_relaxation発火を維持)
    large   : ノード18 × 期18
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_node=4,  n_period=4),
    "default": dict(n_node=12, n_period=12),
    "large":   dict(n_node=18, n_period=18),
}

CP = 4.18          # 熱媒体(水)の比熱 [kJ/(kg K)]
T_ENV = 10.0        # 外気温 [℃]
T_RET = 50.0         # 還流温度 [℃] 一定と仮定(簡易化: 供給側のみ追跡)
T_SOURCE_MIN = 70.0
T_SOURCE_MAX = 120.0
PUMP_EFF = 0.7
C_PUMP = 0.001 / PUMP_EFF
COST_HEAT = 5.0
COST_ELEC = 20.0
SOURCE_RAMP = 8.0    # 熱源出口温度の期あたり最大変化量[℃](熱慣性)


def _data(scale: str):
    cfg = SCALES[scale]
    nNode, nT = cfg["n_node"], cfg["n_period"]
    rng = np.random.default_rng(20260724 + nNode * 41 + nT)

    nodes = list(range(nNode))
    parent = [None] + [int(rng.integers(0, i)) for i in range(1, nNode)]
    edges = [(parent[i], i) for i in range(1, nNode)]

    K_pressure = {e: round(float(rng.uniform(0.3, 0.9)), 3) for e in edges}
    K_heatloss = {e: round(float(rng.uniform(0.06, 0.16)), 3) for e in edges}

    # 需要家の熱需要(日次周期+ノード規模のばらつき)。node0=熱源は需要なし。
    tt = np.arange(nT)
    daily = 1.0 + 0.4 * np.sin(2 * np.pi * tt / max(nT, 2) - 1.2)
    daily = np.clip(daily, 0.35, None)
    base_q = rng.uniform(150.0, 600.0, nNode)
    base_q[0] = 0.0
    q_demand = np.outer(base_q, daily) * (1.0 + rng.uniform(-0.05, 0.05, (nNode, nT)))
    q_demand = np.maximum(q_demand, 0.0)
    q_demand[0, :] = 0.0

    return dict(nNode=nNode, nT=nT, nodes=nodes, edges=edges,
                K_pressure=K_pressure, K_heatloss=K_heatloss, q_demand=q_demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nNode, nT = d["nNode"], d["nT"]
    nodes, edges = d["nodes"], d["edges"]
    K_pressure, K_heatloss, q_demand = d["K_pressure"], d["K_heatloss"], d["q_demand"]

    model = Model("District_Heating_Detailed_Physics")
    N, T = range(nNode), range(nT)

    m_flow = {(e, t): model.addVar(vtype="C", lb=0.0, ub=120.0, name=f"m_{e[0]}_{e[1]}_{t}")
              for e in edges for t in T}
    t_node = {(n, t): model.addVar(vtype="C", lb=50.0, ub=T_SOURCE_MAX, name=f"t_{n}_{t}")
              for n in N for t in T}
    t_out = {(e, t): model.addVar(vtype="C", lb=50.0, ub=T_SOURCE_MAX, name=f"tout_{e[0]}_{e[1]}_{t}")
             for e in edges for t in T}
    dp = {(e, t): model.addVar(vtype="C", lb=0.0, name=f"dp_{e[0]}_{e[1]}_{t}") for e in edges for t in T}
    m_cons = {(n, t): model.addVar(vtype="C", lb=0.0, name=f"mcons_{n}_{t}") for n in N for t in T}
    q_source = {t: model.addVar(vtype="C", lb=0.0, name=f"qsrc_{t}") for t in T}
    w_pump = {t: model.addVar(vtype="C", lb=0.0, name=f"wpump_{t}") for t in T}

    for t in T:
        model.addCons(t_node[0, t] >= T_SOURCE_MIN, name=f"source_tmin_{t}")

        m_source = quicksum(m_flow[e, t] for e in edges if e[0] == 0)

        for n in N:
            if n == 0:
                continue
            m_in = quicksum(m_flow[e, t] for e in edges if e[1] == n)
            m_out_edge = quicksum(m_flow[e, t] for e in edges if e[0] == n)
            # 需要家消費流量: Q_demand = m_cons * cp * (T_node - T_ret) (双線形)
            model.addCons(float(q_demand[n, t]) == m_cons[n, t] * CP * (t_node[n, t] - T_RET),
                          name=f"demand_heat_{n}_{t}")
            model.addCons(m_in == m_out_edge + m_cons[n, t], name=f"mass_balance_{n}_{t}")

        for e in edges:
            # 配管熱損失(双線形): cp*m*(T_in-T_out) = K*(T_in - T_env)
            model.addCons(
                CP * m_flow[e, t] * (t_node[e[0], t] - t_out[e, t])
                == K_heatloss[e] * (t_node[e[0], t] - T_ENV),
                name=f"heat_loss_{e[0]}_{e[1]}_{t}")

        for n in N:
            if n == 0:
                continue
            in_edges = [e for e in edges if e[1] == n]
            if in_edges:
                model.addCons(
                    quicksum(m_flow[e, t] * t_out[e, t] for e in in_edges)
                    == quicksum(m_flow[e, t] for e in in_edges) * t_node[n, t],
                    name=f"temp_mix_{n}_{t}")

        for e in edges:
            model.addCons(dp[e, t] == K_pressure[e] * m_flow[e, t] * m_flow[e, t],
                          name=f"pressure_loss_{e[0]}_{e[1]}_{t}")

        model.addCons(q_source[t] == m_source * CP * (t_node[0, t] - T_RET), name=f"source_heat_{t}")
        model.addCons(
            w_pump[t] == quicksum(m_flow[e, t] * dp[e, t] for e in edges) * C_PUMP,
            name=f"pump_power_{t}")

        if t > 0:
            # 熱源出口温度のランプ制約(熱慣性): 期をまたぐ結合
            model.addCons(t_node[0, t] - t_node[0, t - 1] <= SOURCE_RAMP, name=f"src_ramp_up_{t}")
            model.addCons(t_node[0, t - 1] - t_node[0, t] <= SOURCE_RAMP, name=f"src_ramp_dn_{t}")

    model.setObjective(
        quicksum(COST_HEAT * q_source[t] + COST_ELEC * w_pump[t] for t in T), "minimize")

    model.data = dict(m_flow=m_flow, t_node=t_node, q_source=q_source, w_pump=w_pump,
                      scale=scale, dims=(nNode, len(edges), nT))
    return model


def main() -> None:
    m = build_model("small")
    m.setParam("limits/time", 60)
    m.optimize()
    if m.getNSols() > 0:
        print(f"status: {m.getStatus()}  Optimal-ish Cost: {m.getObjVal():.2f}")
    else:
        print("status:", m.getStatus())


if __name__ == "__main__":
    main()
