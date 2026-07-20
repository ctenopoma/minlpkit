"""週次ユニットコミットメント + 送電混雑(簡易DC潮流) (Weekly UC with Network Congestion).

事業ストーリー
--------------
電力会社の「需給運用部」が、翌週(168時間)の発電ユニット群の起動/停止・出力配分を
決める意思決定である。既存の `samples/scheduling/unit_commitment.py`(4ユニット・非凸
バルブポイント・単一ノード=送電制約なし)を一桁大きい規模(20〜40ユニット級)に拡張し、
かつ**送電網の混雑**を簡易DC潮流(感度係数=PTDF: Power Transfer Distribution Factor)で
表現する。各ユニットは特定のバス(送電網のノード)に接続されており、その出力は
**全ての送電線の潮流制約に(PTDFという線形結合係数を通じて)結合する**。単一ユニットの
起動判断が、離れた送電線の混雑を通じて他の全ユニットの経済性に波及する。

各制約の業務的意味:
- **起動/停止ロジック・最小連続運転/停止・ランプ**: 火力ユニットは急な出力変更や
  頻繁な起動停止ができない(タービンの熱応力・燃焼安定性)。既存UCと同型。
- **予備力(スピニングリザーブ)**: 需要の急変・ユニット脱落に備え、オンラインユニットの
  最大出力合計は需要に安全マージンを乗せた値以上でなければならない。
- **簡易DC潮流(PTDF)による送電混雑**: 送電網は有効電力潮流について線形近似
  (DC power flow)が実務で広く使われる。各送電線の潮流は「全バスの正味注入電力の
  線形結合」(PTDF行列)で決まり、上下限(熱容量)を超えてはならない。これにより、
  ある変電所に接続するユニットの出力を増やすと、ネットワークの反対側にある送電線の
  潮流が変化しうる — **物理的に全ユニットの出力が全送電線制約へ結合する**
  (単なる需要制約の一本化ではなく、感度係数を介した密な結合)。
- **需給バランス**: 系統全体で発電(+電力不足=計画外停電のペナルティ)が需要と一致しなければ
  ならない(DC潮流のPTDFはネット注入の総和ゼロを前提とするため、この等式が必要)。
- **計画外停電(load shedding)バックストップ**: 送電混雑や供給力不足でどうしても需要を
  満たせない場合に、超高コストの計画外停電を許容する(実行可能性の担保)。

なぜ結合が業務要件として自然に入るか:
実際の系統運用者は単一バスの需給バランスだけでなく、送電網の熱容量制約(N-1後の
潮流制限等)を守る義務がある。DC潮流近似はISO/RTOの実務(市場清算・混雑管理)で
標準的に使われる線形結合であり、簡略化ではあるが「全ユニット×全送電線」の密結合構造は
本物である。この密結合と週次(168時間)×数十ユニットの規模そのものが、既存の
単一ノード4ユニットUCにはない難度を生む(FINDINGS: 純粋な整数×連続の分離可能な積は
SCIPに潰されるが、共有資源(ここでは送電網)を介した結合は易しくならない)。

scale ノブ(硬さの源泉: 現実規模(数十ユニット×週次168時間) + 統合意思決定
(起動停止×ネットワーク潮流の同時決定) + 時間結合(ランプ・min up/down)):
    small   : ユニット4  × バス4  × 送電線5  × 12時間   (テスト・ハンズオン用。数分で最適)
    default : ユニット12 × バス7  × 送電線9  × 48時間   (診断の題材。30秒でgap残存)
    large   : ユニット30 × バス16 × 送電線22 × 168時間  (週次・20-40ユニット級の実規模)

    (注: 既定scaleは「30秒analyze」の診断ハーネス実測に基づき調整した値。単純に
    週次168時間×数十ユニットまで広げると mk.analyze の付帯収集器(対称性検出・
    静的診断等)の計算量がSCIP求解時間とは無関係に数百秒規模へ増大するため、
    週次168時間×20-40ユニット級の実規模は large scale 側に残した。)
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_unit=4,  n_bus=4,  n_line=5,  n_period=8),
    "default": dict(n_unit=15, n_bus=8,  n_line=10, n_period=48),
    "large":   dict(n_unit=30, n_bus=16, n_line=22, n_period=168),
}

VOLL = 6000.0  # 計画外停電の価値[$/MWh](非常に高コスト=バックストップ)
RESERVE = 0.15  # スピニングリザーブ率


def _build_network(nB: int, nL: int, rng: np.random.Generator):
    """スパニングツリー+追加コード線でループを持つ送電網を作り、PTDF行列を返す。"""
    edges = []
    for i in range(1, nB):
        j = int(rng.integers(0, i))
        edges.append((j, i))
    # 追加コード線でメッシュ化(ループを作る=PTDFを非自明にする)
    extra = nL - (nB - 1)
    tries = 0
    while len(edges) < nL and tries < 50 * nL:
        i, j = int(rng.integers(0, nB)), int(rng.integers(0, nB))
        tries += 1
        if i == j:
            continue
        pair = (min(i, j), max(i, j))
        if pair in edges or (pair[1], pair[0]) in edges:
            continue
        edges.append(pair)
    nL = len(edges)

    react = rng.uniform(0.05, 0.30, nL)      # 線路リアクタンス[pu]
    suscep = 1.0 / react                     # サセプタンス b_l = 1/x_l

    # バス感受性行列 B (基準バス0を除去して逆行列)
    Bfull = np.zeros((nB, nB))
    for l, (i, j) in enumerate(edges):
        b = suscep[l]
        Bfull[i, i] += b
        Bfull[j, j] += b
        Bfull[i, j] -= b
        Bfull[j, i] -= b
    ref = 0
    idx = [k for k in range(nB) if k != ref]
    Bred = Bfull[np.ix_(idx, idx)]
    Xred = np.linalg.inv(Bred)
    X = np.zeros((nB, nB))
    for a, ia in enumerate(idx):
        for b_, ib in enumerate(idx):
            X[ia, ib] = Xred[a, b_]
    # X[ref, :] = X[:, ref] = 0 (既定でゼロ埋め済み)

    # PTDF[l, k] = b_l * (X[i,k] - X[j,k])
    PTDF = np.zeros((nL, nB))
    for l, (i, j) in enumerate(edges):
        PTDF[l, :] = suscep[l] * (X[i, :] - X[j, :])

    return edges, suscep, PTDF


def _data(scale: str):
    cfg = SCALES[scale]
    nU, nB, nL0, nT = cfg["n_unit"], cfg["n_bus"], cfg["n_line"], cfg["n_period"]
    rng = np.random.default_rng(20260721 + nU * 97 + nB * 31 + nL0 * 11 + nT)

    edges, suscep, PTDF = _build_network(nB, nL0, rng)
    nL = len(edges)

    # 送電線熱容量(タイトにして混雑を強制する)
    cap = np.round(rng.uniform(35, 80, nL), 1)

    # ユニット: バスへランダム配置。小型機ほど多い現実的な混成(石炭/ガス/ピーカー)
    pmin = np.round(rng.uniform(20, 60, nU), 1)
    size = rng.uniform(1.0, 4.0, nU)
    pmax = np.round(pmin + size * rng.uniform(40, 90, nU), 1)
    a_cost = np.round(rng.uniform(120, 400, nU), 1)          # 起動時固定燃料費
    b_cost = np.round(rng.uniform(8, 30, nU), 2)              # 限界費用$/MWh(線形)
    su_cost = np.round(rng.uniform(200, 1500, nU), 1)         # 起動費
    ramp = np.round(pmax * rng.uniform(0.35, 0.6, nU), 1)
    mu = rng.integers(2, 6, nU)                                 # 最小連続運転
    md = rng.integers(1, 4, nU)                                 # 最小連続停止
    bus_of = rng.integers(0, nB, nU)

    # バス別需要: 日次周期(24h)+週末減衰+ノイズ。バスごとの需要シェアをランダムに割当
    hours = np.arange(nT)
    daily = 1.0 + 0.35 * np.sin(2 * np.pi * (hours % 24 - 6) / 24.0)
    daily = np.clip(daily, 0.35, None)
    day_idx = hours // 24
    weekday_factor = np.where((day_idx % 7) < 5, 1.0, 0.82)  # 平日高め・週末減
    system_shape = daily * weekday_factor
    base_total = 0.68 * float(pmax.sum())  # ピーク需要は総設備容量の目安に対する割合
    system_demand = base_total * system_shape * (1.0 + rng.uniform(-0.03, 0.03, nT))

    share = rng.uniform(0.5, 1.5, nB)
    share = share / share.sum()
    demand = np.outer(share, system_demand)  # demand[bus, t]
    demand = np.maximum(demand, 0.0)

    return dict(nU=nU, nB=nB, nL=nL, nT=nT, edges=edges, PTDF=PTDF, cap=cap,
                pmin=pmin, pmax=pmax, a_cost=a_cost, b_cost=b_cost,
                su_cost=su_cost, ramp=ramp, mu=mu, md=md, bus_of=bus_of, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nU, nB, nL, nT = d["nU"], d["nB"], d["nL"], d["nT"]
    edges, PTDF, cap = d["edges"], d["PTDF"], d["cap"]
    pmin, pmax = d["pmin"], d["pmax"]
    a_cost, b_cost, su_cost = d["a_cost"], d["b_cost"], d["su_cost"]
    ramp, mu, md, bus_of = d["ramp"], d["mu"], d["md"], d["bus_of"]
    demand = d["demand"]

    m = Model("Weekly_UC_Ramp_Network")
    U, B, L, T = range(nU), range(nB), range(nL), range(nT)

    u, v, w, p, fc = {}, {}, {}, {}, {}
    for i in U:
        for t in T:
            u[i, t] = m.addVar(vtype="B", name=f"u_{i}_{t}")
            v[i, t] = m.addVar(vtype="B", name=f"v_{i}_{t}")
            w[i, t] = m.addVar(vtype="B", name=f"w_{i}_{t}")
            p[i, t] = m.addVar(vtype="C", lb=0.0, ub=float(pmax[i]), name=f"p_{i}_{t}")
            fc[i, t] = m.addVar(vtype="C", lb=0.0, name=f"fc_{i}_{t}")
    shed = {(b_, t): m.addVar(vtype="C", lb=0.0, ub=float(demand[b_, t]), name=f"shed_{b_}_{t}")
            for b_ in B for t in T}

    for i in U:
        for t in T:
            m.addCons(p[i, t] >= float(pmin[i]) * u[i, t])
            m.addCons(p[i, t] <= float(pmax[i]) * u[i, t])
            prev = u[i, t - 1] if t > 0 else 0
            m.addCons(v[i, t] - w[i, t] == u[i, t] - prev)
            m.addCons(v[i, t] + w[i, t] <= 1)
            if t > 0:
                m.addCons(p[i, t] - p[i, t - 1] <= float(ramp[i]) * u[i, t - 1] + float(pmin[i]) * v[i, t])
                m.addCons(p[i, t - 1] - p[i, t] <= float(ramp[i]) * u[i, t] + float(pmax[i]) * w[i, t])
            for tau in range(t + 1, min(t + int(mu[i]), nT)):
                m.addCons(u[i, tau] >= v[i, t])
            for tau in range(t + 1, min(t + int(md[i]), nT)):
                m.addCons(u[i, tau] <= 1 - w[i, t])
            # 燃料費は線形(限界費用一定)とし、非線形コストは持たせない。
            # 難度の源泉は二次コストではなく PTDF による送電網結合と週次規模のMILP組合せ。
            m.addCons(fc[i, t] >= float(a_cost[i]) * u[i, t] + float(b_cost[i]) * p[i, t])

    # 系統全体の需給バランス(PTDFの前提=正味注入の総和ゼロ)
    for t in T:
        m.addCons(quicksum(p[i, t] for i in U) + quicksum(shed[b_, t] for b_ in B)
                  == float(demand[:, t].sum()), name=f"balance_{t}")
        # スピニングリザーブ: オンラインユニットの最大出力合計 >= 実供給量*(1+reserve)
        # (計画外停電で賄った分には予備力は不要 = 実際に電力網から供給する量が基準)
        served = float(demand[:, t].sum()) - quicksum(shed[b_, t] for b_ in B)
        m.addCons(quicksum(float(pmax[i]) * u[i, t] for i in U)
                  >= served * (1 + RESERVE), name=f"reserve_{t}")

    # バスごとの発電合計(PTDF結合用)
    gen_at_bus = {(b_, t): quicksum(p[i, t] for i in U if int(bus_of[i]) == b_)
                  for b_ in B for t in T}

    # 簡易DC潮流: 各送電線の潮流 = Σ_bus PTDF[l,bus]*(発電-需要+停電)
    for l in L:
        for t in T:
            net = quicksum(float(PTDF[l, b_]) * (gen_at_bus[b_, t] - float(demand[b_, t]) + shed[b_, t])
                           for b_ in B)
            m.addCons(net <= float(cap[l]), name=f"flow_ub_{l}_{t}")
            m.addCons(net >= -float(cap[l]), name=f"flow_lb_{l}_{t}")

    obj = quicksum(fc[i, t] + float(su_cost[i]) * v[i, t] for i in U for t in T)
    obj += quicksum(VOLL * shed[b_, t] for b_ in B for t in T)
    m.setObjective(obj, "minimize")

    m.data = dict(u=u, p=p, shed=shed, scale=scale, dims=(nU, nB, nL, nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
