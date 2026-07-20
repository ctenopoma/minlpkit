"""ガス圧送ネットワークの運用計画 (Gas Pipeline Network with Weymouth Flow-Pressure).

事業ストーリー
--------------
都市ガス/天然ガス輸送会社の「圧送運用部」が、1日(または数日)を通じて、供給拠点からの
基本供給量、各コンプレッサ(圧送機)の起動/停止と昇圧量、そして緊急時の局所ピークシェイビング
供給を決める意思決定である。パイプライン内の流量と圧力の関係は **Weymouth式**
(流量² ∝ 圧力²の差)という本質的に非凸な物理式に従い、コンプレッサの運転可否(整数)が
昇圧量(連続)と共に流量(連続)にも影響する(整数×連続の結合)。

各制約の業務的意味:
- **Weymouth式(非凸)**: 定常状態のガス管内で、流量の2乗は上流圧力の2乗と下流圧力の2乗の
  差に比例する(f² = K·(p_up² − p_down²))。これは近似ではなく圧縮性流体の管内摩擦損失の
  古典的な工学式であり、二次式どうしの差という**非凸な等式制約**を生む。
- **コンプレッサの on/off(整数)+ 昇圧量(連続)**: 遠方の需要地点まで規定圧力を届けるには
  途中でコンプレッサにより昇圧する必要がある。稼働しなければ昇圧量は0(=上流圧力をそのまま
  下流管へ渡す)、稼働すれば昇圧量は連続変数として選べるが、その分の**消費エネルギー
  (流量×昇圧量の双線形)**を消費し電力費がかかる。稼働には最低通過流量も必要(遊休運転はしない)。
- **需要地点の圧力下限(納入SLA)**: 各需要家は契約上、末端での最低供給圧力を保証される
  必要がある(圧力が低いとガス機器が正常動作しない)。
- **配管内ガス在庫(ラインパック、時間結合)**: 圧縮性気体であるガスは配管内にも
  在庫として溜め込める(linepack)。配管の在庫量は概ね平均圧力に比例し、その期毎の増減が
  「入口流量 − 出口流量」と一致する(在庫問題と同型の時間結合)。実務ではこのラインパックを
  日中の需要ピークに合わせて計画的に増減させる(夜間に貯めて昼間に取り崩す)ため、
  各期の圧送判断が独立に分解できず、需要山谷を見通した多期同時決定になる。
- **基本供給+ローカル・ピークシェイビング供給(バックストップ)**: 供給源からの基本供給量には
  上限があり、Weymouth+コンプレッサの制御だけでは末端の圧力SLAを満たせない期がありうる。
  その場合、各地点でLNGサテライト等による高コストの局所供給を許容し、常時実行可能性を担保する。

なぜ非凸が業務要件として自然に入るか:
Weymouth式は近似ではなく実際の輸送実務(SCADA・圧送計画)で使われる物理式そのものであり、
圧力の2乗差という非凸構造を回避することはできない。コンプレッサの起動判断と昇圧量の
同時決定(整数×連続)は圧送網運用の中核的意思決定であり、これも単純化できない。ラインパックの
時間結合も気体の圧縮性という物理そのものであり、期別に切り離して解くと現実の運用にならない。

scale ノブ(硬さの源泉: 物理結合(Weymouth+コンプレッサの流量×昇圧双線形) + 時間結合
(ラインパック在庫) + 統合意思決定(コンプレッサon/off×昇圧量) + 現実規模(多期×多コンプレッサ)):
    small   : ノード5  × コンプレッサ1 × 6期    (テスト・ハンズオン用。数分で最適)
    default : ノード13 × コンプレッサ4 × 30期   (診断の題材。30秒でgap残存)
    large   : ノード17 × コンプレッサ5 × 48期
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_node=4,  n_comp=1, n_period=3),
    "default": dict(n_node=6,  n_comp=2, n_period=10),
    "large":   dict(n_node=17, n_comp=5, n_period=48),
}

BASE_COST = 3.0          # 基本供給単価[$/千m3]
BACKSTOP_COST = 220.0    # 局所ピークシェイビング供給単価(高コストのバックストップ)
ENERGY_COST = 6.0        # コンプレッサ消費エネルギー単価[$/(圧力単位・流量単位)]
COMP_IDLE_COST = 25.0    # コンプレッサ稼働の最低運転コスト(遊休でも発生)


def _data(scale: str):
    cfg = SCALES[scale]
    nN, nC, nT = cfg["n_node"], cfg["n_comp"], cfg["n_period"]
    rng = np.random.default_rng(20260723 + nN * 61 + nC * 13 + nT)

    # 放射状(木)ネットワーク: node0=供給源, i=1..nN-1 は親をランダムに選んで接続
    parent = [None] + [int(rng.integers(0, i)) for i in range(1, nN)]
    edges = [(parent[i], i) for i in range(1, nN)]
    nE = len(edges)

    # Weymouth係数(管径・長さに応じてばらつき)
    Kw = np.round(rng.uniform(0.35, 0.95, nE), 3)
    # ラインパック係数(配管容積に相当。在庫量[千m3] = Clp * 平均圧力)
    Clp = np.round(rng.uniform(0.9, 2.2, nE), 3)

    # ノード圧力範囲: 供給源は高圧に制御可能、末端ほど納入圧力SLA(下限)を持つ
    pmax_node = np.round(rng.uniform(70, 90, nN), 1)
    pmax_node[0] = 95.0
    pmin_deliv = np.round(rng.uniform(28, 45, nN), 1)
    pmin_deliv[0] = 60.0  # 供給源自体の運用下限

    # コンプレッサをコード(木の枝)のうち需要家側(nE個からランダムに nC 本)に設置
    comp_edges = list(rng.choice(nE, size=min(nC, nE), replace=False))
    boost_max = {e: round(float(rng.uniform(18, 30)), 1) for e in comp_edges}
    comp_min_flow = {e: round(float(rng.uniform(3.0, 6.0)), 1) for e in comp_edges}

    # 需要パターン(日次周期+ノード毎の需要規模)。node0(供給源)は需要なし
    tt = np.arange(nT)
    daily = 1.0 + 0.45 * np.sin(2 * np.pi * (tt % 24 - 7) / 24.0)
    daily = np.clip(daily, 0.25, None)
    base_demand = rng.uniform(3.0, 9.0, nN)
    base_demand[0] = 0.0
    demand = np.outer(base_demand, daily) * (1.0 + rng.uniform(-0.05, 0.05, (nN, nT)))
    demand = np.maximum(demand, 0.0)
    demand[0, :] = 0.0

    supply_cap = float(demand.sum(axis=0).max()) * 0.72  # 基本供給だけでは不足する期を作る

    return dict(nN=nN, nT=nT, edges=edges, Kw=Kw, Clp=Clp, pmax_node=pmax_node,
                pmin_deliv=pmin_deliv, comp_edges=comp_edges, boost_max=boost_max,
                comp_min_flow=comp_min_flow, demand=demand, supply_cap=supply_cap)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nN, nT = d["nN"], d["nT"]
    edges, Kw, Clp = d["edges"], d["Kw"], d["Clp"]
    pmax_node, pmin_deliv = d["pmax_node"], d["pmin_deliv"]
    comp_edges, boost_max, comp_min_flow = d["comp_edges"], d["boost_max"], d["comp_min_flow"]
    demand, supply_cap = d["demand"], d["supply_cap"]

    m = Model("Gas_Pipeline_Weymouth")
    N, T = range(nN), range(nT)
    E = range(len(edges))

    p = {(n, t): m.addVar(vtype="C", lb=float(pmin_deliv[n]), ub=float(pmax_node[n]),
                          name=f"p_{n}_{t}") for n in N for t in T}
    pu = {(e, t): m.addVar(vtype="C", lb=0.0, ub=float(pmax_node[edges[e][0]]) + (
        boost_max.get(e, 0.0)), name=f"pu_{e}_{t}") for e in E for t in T}
    # 配管の入口流量(圧縮機直後)と出口流量(下流ノードへ)を別変数にし、
    # ラインパック(在庫)を介して時間結合させる
    fin = {(e, t): m.addVar(vtype="C", lb=0.0, ub=40.0, name=f"fin_{e}_{t}") for e in E for t in T}
    fout = {(e, t): m.addVar(vtype="C", lb=0.0, ub=40.0, name=f"fout_{e}_{t}") for e in E for t in T}
    lp = {(e, t): m.addVar(vtype="C", lb=0.0, name=f"lp_{e}_{t}") for e in E for t in T}
    y = {(e, t): m.addVar(vtype="B", name=f"y_{e}_{t}") for e in comp_edges for t in T}
    power = {(e, t): m.addVar(vtype="C", lb=0.0, name=f"power_{e}_{t}")
             for e in comp_edges for t in T}
    inject = {t: m.addVar(vtype="C", lb=0.0, ub=float(supply_cap), name=f"inject_{t}") for t in T}
    backstop = {(n, t): m.addVar(vtype="C", lb=0.0, name=f"backstop_{n}_{t}") for n in N for t in T}

    for t in T:
        for e in E:
            i, j = edges[e]
            if e in comp_edges:
                bm = float(boost_max[e])
                m.addCons(pu[e, t] >= p[i, t], name=f"boost_lb_{e}_{t}")
                m.addCons(pu[e, t] <= p[i, t] + bm * y[e, t], name=f"boost_ub_{e}_{t}")
                m.addCons(fin[e, t] >= float(comp_min_flow[e]) * y[e, t], name=f"comp_minflow_{e}_{t}")
                # 消費エネルギー = 流量 × 昇圧量 (双線形。y=0なら pu=p[i,t] となり自動的に0)
                m.addCons(power[e, t] == fin[e, t] * (pu[e, t] - p[i, t]), name=f"comp_power_{e}_{t}")
            else:
                m.addCons(pu[e, t] == p[i, t], name=f"no_comp_pu_{e}_{t}")
            # Weymouth式(平均流量で評価): avg_f^2 = K*(上流圧力^2 - 下流圧力^2) (非凸等式)
            avgf = 0.5 * (fin[e, t] + fout[e, t])
            m.addCons(avgf * avgf == float(Kw[e]) * (pu[e, t] * pu[e, t] - p[j, t] * p[j, t]),
                      name=f"weymouth_{e}_{t}")
            # ラインパック(配管内ガス在庫) = 係数 * 平均圧力
            m.addCons(lp[e, t] == float(Clp[e]) * 0.5 * (pu[e, t] + p[j, t]), name=f"linepack_def_{e}_{t}")
            if t == 0:
                # 初期状態は定常(入口流量=出口流量)とみなす
                m.addCons(fin[e, t] == fout[e, t], name=f"linepack_init_{e}")
            else:
                m.addCons(lp[e, t] - lp[e, t - 1] == fin[e, t] - fout[e, t], name=f"linepack_bal_{e}_{t}")

        # ノード流量収支: 流入(下流端到着分)- 流出(上流端送出分) + 注入 = 需要
        for n in N:
            in_flow = quicksum(fout[e, t] for e in E if edges[e][1] == n)
            out_flow = quicksum(fin[e, t] for e in E if edges[e][0] == n)
            src = inject[t] if n == 0 else 0.0
            m.addCons(in_flow - out_flow + src + backstop[n, t] - float(demand[n, t]) == 0.0,
                      name=f"node_balance_{n}_{t}")

    obj = quicksum(BASE_COST * inject[t] for t in T)
    obj += quicksum(BACKSTOP_COST * backstop[n, t] for n in N for t in T)
    obj += quicksum(ENERGY_COST * power[e, t] + COMP_IDLE_COST * y[e, t]
                    for e in comp_edges for t in T)
    m.setObjective(obj, "minimize")

    m.data = dict(p=p, fin=fin, fout=fout, y=y, inject=inject, backstop=backstop, scale=scale,
                  dims=(nN, len(edges), len(comp_edges), nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
