"""交流最適潮流(AC-OPF)+ 離散無効電力補償 (AC Optimal Power Flow, MINLP).

事業ストーリー
--------------
送電系統運用者(ISO/RTO・電力会社の給電指令所)が、各発電機の有効/無効出力と
各バスの電圧を決め、需要を満たしながら**発電費用**(または送電損失)を最小化する
意思決定である。`weekly_uc_ramp.py` の簡易DC潮流(有効電力のみ・線形)を、
**真の交流(AC)潮流**へ格上げした対比題材に位置づける。

なぜ AC(DCでなく)が業務上重要か
--------------------------------
DC近似は有効電力の混雑管理には十分だが、以下は**真の潮流計算(AC)でしか見えない**:
- **電圧の大きさ** V_i: 機器の耐圧・需要家品質のため 0.9〜1.1 pu 等に収めねばならない。
  DC近似は全電圧を 1.0 pu と仮定するため電圧違反を一切検出できない。
- **無効電力** Q: 電圧を支える"通貨"。無効電力が不足するバスは電圧が沈む。
  発電機の無効出力・**離散的な無効電力補償(コンデンサバンク)**の投入で支える。
- **送電損失**: 線路抵抗 R による I²R 損失は電圧×電圧×cos で決まる真の非線形量で、
  DC近似(損失ゼロ)では評価できない。損失最小化・電圧維持は AC でしか扱えない。

定式化(極座標形式)
--------------------
各バス i に電圧の大きさ V_i と位相角 θ_i(連続変数、基準バスは θ=0 に固定)を置く。
アドミタンス行列 Y = G + jB(G=コンダクタンス, B=サセプタンス)を通じ、
バス i の正味注入電力は **電圧×電圧×三角関数の真の非凸**で表される:

    P_i = V_i * Σ_{j∈N(i)∪{i}} V_j (G_ij cos(θ_i-θ_j) + B_ij sin(θ_i-θ_j))
    Q_i = V_i * Σ_{j∈N(i)∪{i}} V_j (G_ij sin(θ_i-θ_j) - B_ij cos(θ_i-θ_j))

電力バランス(各バス):
    Pg_i - Pd_i          = P_i(V, θ)
    Qg_i - Qd_i + Qc_i   = Q_i(V, θ)

ここで Qc_i = qstep · n_i は **離散コンデンサバンク**による無効電力補償で、
n_i ∈ {0,1,...,K} が本モデルの整数決定(MINLP化の核心)。無効補償の投入段数を
選ぶことでバス電圧を規定範囲に保ちつつ損失/費用を下げる、という実務上の離散意思決定。
(整数変数は無効バランスに**線形**に入るため、真の非凸は V·V·cos/sin 側に集約され、
 実行可能解探索が破綻しにくい。送電線 on/off や離散タップはアドミタンス自体を離散化し
 非凸項に整数を掛け込むためさらに難しく、まず本形で定式化パターンを確立する。)

目的: Σ_i (a_i + b_i·Pg_i + c_i·Pg_i²) の発電費用最小化。

PySCIPOpt での sin/cos
----------------------
`from pyscipopt import sin, cos` が利用可能(6.2.1 で確認)。θ_i-θ_j はアフィン式で、
`cos(theta[i]-theta[j])` が非線形式ノードを生成し、SCIP が空間分枝限定法で厳密に扱う。
Ybus のスパース性を使い、隣接バスと自己項のみ和をとる(密和は避ける)。

実行可能性の確保で効いた工夫(honest log は results/acceptance_t9.md 参照)
--------------------------------------------------------------------------
- 位相角差を ±30°(±π/6)に制限(フラットスタート θ=0 近傍で cos>0・sin 単調)。
- 電圧境界は small で [0.90, 1.12] とやや広め(default は [0.94, 1.06])。
- 発電容量に十分な余裕(Σ Pgmax ≈ ピーク需要の 2 倍超)。無効も潤沢な Qg 限界+
  コンデンサバンクで支える。
- 基準バス θ=0 固定、V は各バス境界内可変(スラック発電機がミスマッチを吸収)。

scale ノブ
    small   : 5 バス(実行可能解が出ることの確認用。真の非凸だが小規模)
    default : 14 バス(IEEE 14 相当規模。診断・空間分枝木の題材)
    large   : 30 バス(IEEE 30 相当規模)
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum, sin, cos

SCALES = {
    "small":   dict(n_bus=5,  n_extra=1, vlo=0.90, vhi=1.12),
    "default": dict(n_bus=14, n_extra=6, vlo=0.94, vhi=1.06),
    "large":   dict(n_bus=30, n_extra=12, vlo=0.94, vhi=1.06),
}

ANGLE_LIM = np.pi / 6.0     # 位相角の絶対上限 [rad] (=30deg)
PF = 0.90                    # 負荷力率 → Qd = Pd*tan(acos(PF))
QSTEP = 0.10                 # コンデンサバンク1段の無効出力 [pu]
CAP_MAX = 5                  # バンク最大段数(整数変数の上限)


def _build_network(nB: int, n_extra: int, rng: np.random.Generator):
    """スパニングツリー + 追加線でループを持つ送電網を作り Ybus(G,B) を返す。"""
    edges = []
    for i in range(1, nB):
        j = int(rng.integers(0, i))
        edges.append((j, i))
    tries = 0
    while len(edges) < (nB - 1) + n_extra and tries < 100 * nB:
        i, j = int(rng.integers(0, nB)), int(rng.integers(0, nB))
        tries += 1
        if i == j:
            continue
        pair = (min(i, j), max(i, j))
        if pair in edges:
            continue
        edges.append(pair)

    # 直列インピーダンス z = r + jx → 直列アドミタンス y = 1/z = g + jb
    r = rng.uniform(0.01, 0.06, len(edges))
    x = rng.uniform(0.05, 0.25, len(edges))
    bsh = rng.uniform(0.01, 0.04, len(edges))   # 線路充電(対地サセプタンス/2)
    denom = r * r + x * x
    g = r / denom
    b = -x / denom

    G = np.zeros((nB, nB))
    B = np.zeros((nB, nB))
    for l, (i, j) in enumerate(edges):
        G[i, i] += g[l]
        G[j, j] += g[l]
        G[i, j] -= g[l]
        G[j, i] -= g[l]
        B[i, i] += b[l] + bsh[l]
        B[j, j] += b[l] + bsh[l]
        B[i, j] -= b[l]
        B[j, i] -= b[l]

    neighbors = {i: [] for i in range(nB)}
    for (i, j) in edges:
        neighbors[i].append(j)
        neighbors[j].append(i)
    return edges, G, B, neighbors


def _data(scale: str):
    cfg = SCALES[scale]
    nB, n_extra = cfg["n_bus"], cfg["n_extra"]
    rng = np.random.default_rng(20260720 + nB * 131 + n_extra * 17)

    edges, G, B, neighbors = _build_network(nB, n_extra, rng)

    # 発電機バス: 基準バス0を含め ~40% に配置
    n_gen = max(2, int(round(0.4 * nB)))
    gen_buses = [0] + sorted(rng.choice(range(1, nB), size=n_gen - 1, replace=False).tolist())

    # 負荷(有効 Pd, 無効 Qd)。発電バスにも負荷はありうる。基準バスは負荷小さめ。
    Pd = rng.uniform(0.15, 0.55, nB)
    Pd[0] *= 0.3
    tan_phi = np.tan(np.arccos(PF))
    Qd = Pd * tan_phi

    # 発電機コスト・容量。総容量はピーク需要の 2 倍超の余裕。
    total_pd = float(Pd.sum())
    pgmax = {}
    pgmin = {}
    a_cost, b_cost, c_cost = {}, {}, {}
    qgmax, qgmin = {}, {}
    for gb in gen_buses:
        pgmax[gb] = round(float(rng.uniform(0.8, 1.4) * total_pd / max(1, len(gen_buses) - 0) + 0.4), 3)
        pgmin[gb] = 0.0
        a_cost[gb] = round(float(rng.uniform(0.0, 5.0)), 3)
        b_cost[gb] = round(float(rng.uniform(15.0, 40.0)), 3)
        c_cost[gb] = round(float(rng.uniform(1.0, 6.0)), 3)
        qgmax[gb] = round(float(rng.uniform(0.4, 0.9)), 3)
        qgmin[gb] = -round(float(rng.uniform(0.3, 0.6)), 3)

    # コンデンサバンク候補: 発電機の無い負荷バス(無効支援が要る所)
    cap_buses = [i for i in range(nB) if i not in gen_buses]

    return dict(nB=nB, edges=edges, G=G, B=B, neighbors=neighbors,
                gen_buses=gen_buses, cap_buses=cap_buses, Pd=Pd, Qd=Qd,
                pgmax=pgmax, pgmin=pgmin, qgmax=qgmax, qgmin=qgmin,
                a_cost=a_cost, b_cost=b_cost, c_cost=c_cost,
                vlo=cfg["vlo"], vhi=cfg["vhi"])


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nB = d["nB"]
    G, B, neighbors = d["G"], d["B"], d["neighbors"]
    gen_buses, cap_buses = d["gen_buses"], d["cap_buses"]
    Pd, Qd = d["Pd"], d["Qd"]
    vlo, vhi = d["vlo"], d["vhi"]

    m = Model("AC_OPF")
    Bx = range(nB)

    # 電圧の大きさ V_i, 位相角 θ_i(基準バス0は θ=0 固定)
    V = {i: m.addVar(vtype="C", lb=vlo, ub=vhi, name=f"V_{i}") for i in Bx}
    th = {}
    for i in Bx:
        if i == 0:
            th[i] = m.addVar(vtype="C", lb=0.0, ub=0.0, name="theta_0")
        else:
            th[i] = m.addVar(vtype="C", lb=-ANGLE_LIM, ub=ANGLE_LIM, name=f"theta_{i}")

    # 発電機の有効/無効出力
    Pg = {gb: m.addVar(vtype="C", lb=d["pgmin"][gb], ub=d["pgmax"][gb], name=f"Pg_{gb}")
          for gb in gen_buses}
    Qg = {gb: m.addVar(vtype="C", lb=d["qgmin"][gb], ub=d["qgmax"][gb], name=f"Qg_{gb}")
          for gb in gen_buses}

    # 離散コンデンサバンク段数(整数決定)。Qc_i = QSTEP * n_i
    ncap = {cb: m.addVar(vtype="I", lb=0, ub=CAP_MAX, name=f"ncap_{cb}") for cb in cap_buses}

    def P_inj(i):
        """バス i の正味有効注入 P_i(V,θ) = V_i Σ_j V_j (G cos + B sin)。"""
        terms = [V[i] * (G[i, i] * V[i])]  # j=i, θ差=0 → cos=1, sin=0
        for j in neighbors[i]:
            dth = th[i] - th[j]
            terms.append(V[i] * V[j] * (G[i, j] * cos(dth) + B[i, j] * sin(dth)))
        return quicksum(terms)

    def Q_inj(i):
        """バス i の正味無効注入 Q_i(V,θ) = V_i Σ_j V_j (G sin - B cos)。"""
        terms = [V[i] * (-B[i, i] * V[i])]  # j=i, θ差=0 → sin=0, cos=1
        for j in neighbors[i]:
            dth = th[i] - th[j]
            terms.append(V[i] * V[j] * (G[i, j] * sin(dth) - B[i, j] * cos(dth)))
        return quicksum(terms)

    for i in Bx:
        pg_i = Pg[i] if i in gen_buses else 0.0
        qg_i = Qg[i] if i in gen_buses else 0.0
        qc_i = (QSTEP * ncap[i]) if i in cap_buses else 0.0
        m.addCons(pg_i - float(Pd[i]) == P_inj(i), name=f"pbal_{i}")
        m.addCons(qg_i - float(Qd[i]) + qc_i == Q_inj(i), name=f"qbal_{i}")

    # 発電費用は二次(凸)。SCIP は非線形目的を直接扱えないため補助変数の epigraph に置く。
    cgen = {gb: m.addVar(vtype="C", lb=0.0, name=f"cost_{gb}") for gb in gen_buses}
    for gb in gen_buses:
        m.addCons(cgen[gb] >= float(d["a_cost"][gb]) + float(d["b_cost"][gb]) * Pg[gb]
                  + float(d["c_cost"][gb]) * Pg[gb] * Pg[gb], name=f"cost_{gb}")
    m.setObjective(quicksum(cgen[gb] for gb in gen_buses), "minimize")

    m.data = dict(V=V, theta=th, Pg=Pg, Qg=Qg, ncap=ncap, scale=scale,
                  gen_buses=gen_buses, cap_buses=cap_buses, dims=(nB, len(d["edges"])))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"gen cost: {m.getObjVal():.4f}")
        V = m.data["V"]
        print("voltages:", [round(m.getVal(V[i]), 3) for i in range(m.data['dims'][0])])
        ncap = m.data["ncap"]
        print("cap banks:", {cb: int(round(m.getVal(ncap[cb]))) for cb in m.data["cap_buses"]})


if __name__ == "__main__":
    main()
