"""送電線増強計画 + 増強後運用の同時決定 (Transmission Expansion Planning with Operation).

事業ストーリー
--------------
電力広域系統運用機関の「系統計画者」が、複数年に一度の投資計画サイクルで「どの候補送電線
(コリドー)を新設・増強するか」(整数)を決め、その増強後の系統で「複数の需要シナリオ
それぞれに対する給電運用(DC潮流)」(連続)を同時に検討する意思決定である。

各制約の業務的意味:
- **既存送電網(必ず稼働)**: 現状の送電網は容量が小さく、需要の伸びに対して慢性的に
  混雑している。既存線は常に物理法則(潮流=感受率×位相角差)に従う。
- **候補線の増強決定(整数×連続の結合、disjunctive形式)**: 候補コリドーを増強すると
  「新しい物理的な送電経路」が生まれ、そこに感受率に応じた潮流が流れるようになる
  (Kirchhoffの電圧則)。増強しなければ潮流はゼロ(容量制約でも縛られる)。この
  「建設可否が物理法則そのものを有効化するかどうかを切り替える」という disjunctive
  構造(big-M)が古典的送電拡張計画(TEP)の定式化であり、単純な容量拡大とは異なり
  整数決定が連続変数の可行領域自体を変える真の結合を生む。
- **複数需要シナリオへのロバスト性**: 実際の投資は「ある1つの需要見通し」だけでなく、
  複数シナリオ(猛暑ピーク・平常時・低需要期など)のいずれが実現しても系統が運用可能で
  なければならない。増強決定 `build[c]` は全シナリオで共有される一方、発電配分・
  位相角・計画外停電はシナリオごとに独立して最適化される — 典型的な2段階ロバスト
  計画の構造(1段階目=投資、2段階目=シナリオ別運用)。
- **計画外停電(load shedding)バックストップ**: どのシナリオでも増強・発電だけでは
  賄いきれない場合に高コストの計画外停電を許容し、常時実行可能性を担保する。
- **発電費用**: 発電所ごとに限界費用が異なり(安価な発電地点は需要中心から離れている
  ことが多く、まさにそれが送電投資の必要性を生む)、シナリオごとの経済配分を行う。

なぜ結合が業務要件として自然に入るか:
送電投資はいったん決めれば数十年単位で固定される「意思決定の橋」であり、その後の
毎時運用(発電配分)は増強された物理ネットワークの中でしか行えない。既存線だけでは
慢性的に混雑し、需要シナリオによって「どのコリドーを増強すべきか」の望ましさが変わる
ため、複数シナリオを同時に満たす投資の組合せ最適化(TEP)は本質的にNP困難な統合
意思決定である(単一シナリオなら容量計画は易しいが、シナリオ間でトレードオフが
生じて初めて難度が出る)。

scale ノブ(硬さの源泉: 統合意思決定(候補線増強×シナリオ別運用の同時決定、disjunctive
結合) + 現実規模(バス数×候補コリドー数×シナリオ数)):
    small   : バス5  × 候補線4 × シナリオ3   (テスト・ハンズオン用。数分で最適)
    default : バス9  × 候補線8 × シナリオ5   (診断の題材。30秒でgap残存)
    large   : バス16 × 候補線16 × シナリオ8
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_bus=5,  n_candidate=4,  n_scenario=3),
    "default": dict(n_bus=9,  n_candidate=8,  n_scenario=5),
    "large":   dict(n_bus=16, n_candidate=16, n_scenario=8),
}

VOLL = 8000.0        # 計画外停電の価値[$/MWh](非常に高コスト=バックストップ)
BIG_M = 400.0         # disjunctive big-M(位相角差×感受率の取りうる範囲を十分覆う)


def _spanning_tree(nB: int, rng: np.random.Generator) -> list[tuple[int, int]]:
    edges = []
    for i in range(1, nB):
        j = int(rng.integers(0, i))
        edges.append((j, i))
    return edges


def _data(scale: str):
    cfg = SCALES[scale]
    nB, nC, nS = cfg["n_bus"], cfg["n_candidate"], cfg["n_scenario"]
    rng = np.random.default_rng(20260723 + nB * 71 + nC * 13 + nS * 5)

    # 既存網: スパニングツリーのみ(容量を小さくして慢性的に混雑させる)
    existing = _spanning_tree(nB, rng)
    nE = len(existing)
    b_exist = rng.uniform(3.0, 6.0, nE)
    cap_exist = np.round(rng.uniform(15, 30, nE), 1)

    # 候補コリドー(既存にないバスペアを追加。ループを作り増強の選択肢を非自明にする)
    existing_set = {tuple(sorted(e)) for e in existing}
    cand_edges = []
    tries = 0
    while len(cand_edges) < nC and tries < 200 * nC:
        i, j = int(rng.integers(0, nB)), int(rng.integers(0, nB))
        tries += 1
        if i == j:
            continue
        pair = tuple(sorted((i, j)))
        if pair in existing_set or pair in cand_edges:
            continue
        cand_edges.append(pair)
    nC = len(cand_edges)
    b_cand = rng.uniform(4.0, 8.0, nC)
    cap_cand = np.round(rng.uniform(25, 55, nC), 1)
    invest_cost = np.round(cap_cand * rng.uniform(45, 80, nC), 1)

    # 発電機: 一部のバスにのみ配置(安価な発電地点が需要中心から離れている=送電投資を要する)
    n_gen_bus = max(2, nB // 3)
    gen_bus = rng.choice(nB, size=n_gen_bus, replace=False)
    gen_cap = np.round(rng.uniform(40, 90, n_gen_bus), 1)
    gen_cost = np.round(rng.uniform(15, 55, n_gen_bus), 2)

    # シナリオ別需要: 基準パターンにシナリオごとの倍率・バス別配分を変えてロバスト性を要求
    base_share = rng.uniform(0.5, 1.5, nB)
    base_share = base_share / base_share.sum()
    scenario_scale = np.linspace(0.80, 1.05, nS)  # 低需要期〜猛暑ピークまで(発電総容量は常に上回る)
    scenario_weight = np.round(rng.uniform(0.6, 1.4, nS), 2)
    total_gen_cap = float(gen_cap.sum())
    demand = np.zeros((nS, nB))
    for s in range(nS):
        share = base_share * (1.0 + rng.uniform(-0.15, 0.15, nB))
        share = np.maximum(share, 0.01)
        share = share / share.sum()
        demand[s] = share * total_gen_cap * 0.80 * scenario_scale[s]

    return dict(nB=nB, nE=nE, nC=nC, nS=nS, existing=existing, cand_edges=cand_edges,
                b_exist=b_exist, cap_exist=cap_exist, b_cand=b_cand, cap_cand=cap_cand,
                invest_cost=invest_cost, gen_bus=gen_bus, gen_cap=gen_cap,
                gen_cost=gen_cost, demand=demand, scenario_weight=scenario_weight)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nB, nE, nC, nS = d["nB"], d["nE"], d["nC"], d["nS"]
    existing, cand_edges = d["existing"], d["cand_edges"]
    b_exist, cap_exist = d["b_exist"], d["cap_exist"]
    b_cand, cap_cand, invest_cost = d["b_cand"], d["cap_cand"], d["invest_cost"]
    gen_bus, gen_cap, gen_cost = d["gen_bus"], d["gen_cap"], d["gen_cost"]
    demand, scenario_weight = d["demand"], d["scenario_weight"]

    m = Model("Transmission_Expansion_Operation")
    B, E, C, S = range(nB), range(nE), range(nC), range(nS)
    G = range(len(gen_bus))
    REF = 0
    THETA_MAX = 0.5  # [rad] 位相角差の実務的な上限(数値安定化)

    build = {c: m.addVar(vtype="B", name=f"build_{c}") for c in C}

    theta, flow_e, flow_c, gen, shed = {}, {}, {}, {}, {}
    for s in S:
        for b_ in B:
            lb = 0.0 if b_ == REF else -THETA_MAX
            ub = 0.0 if b_ == REF else THETA_MAX
            theta[b_, s] = m.addVar(vtype="C", lb=lb, ub=ub, name=f"theta_{b_}_{s}")
        for e in E:
            flow_e[e, s] = m.addVar(vtype="C", lb=-float(cap_exist[e]), ub=float(cap_exist[e]),
                                    name=f"flow_e_{e}_{s}")
        for c in C:
            flow_c[c, s] = m.addVar(vtype="C", lb=-float(cap_cand[c]), ub=float(cap_cand[c]),
                                    name=f"flow_c_{c}_{s}")
        for g in G:
            gen[g, s] = m.addVar(vtype="C", lb=0.0, ub=float(gen_cap[g]), name=f"gen_{g}_{s}")
        for b_ in B:
            shed[b_, s] = m.addVar(vtype="C", lb=0.0, ub=float(demand[s, b_]), name=f"shed_{b_}_{s}")

    for s in S:
        # 既存線: 常に物理法則(潮流=感受率×位相角差)に従う
        for e, (i, j) in enumerate(existing):
            m.addCons(flow_e[e, s] == float(b_exist[e]) * (theta[i, s] - theta[j, s]),
                      name=f"kirchhoff_exist_{e}_{s}")
        # 候補線: disjunctive(増強すれば物理法則が有効化、しなければ潮流ゼロ)
        for c, (i, j) in enumerate(cand_edges):
            m.addCons(flow_c[c, s] <= float(cap_cand[c]) * build[c], name=f"cand_cap_ub_{c}_{s}")
            m.addCons(flow_c[c, s] >= -float(cap_cand[c]) * build[c], name=f"cand_cap_lb_{c}_{s}")
            m.addCons(
                flow_c[c, s] - float(b_cand[c]) * (theta[i, s] - theta[j, s])
                <= BIG_M * (1 - build[c]), name=f"kirchhoff_cand_ub_{c}_{s}")
            m.addCons(
                flow_c[c, s] - float(b_cand[c]) * (theta[i, s] - theta[j, s])
                >= -BIG_M * (1 - build[c]), name=f"kirchhoff_cand_lb_{c}_{s}")

        # バスごとの需給バランス(発電+流入-流出+停電=需要)
        for b_ in B:
            inflow = quicksum(flow_e[e, s] for e, (i, j) in enumerate(existing) if j == b_) \
                - quicksum(flow_e[e, s] for e, (i, j) in enumerate(existing) if i == b_) \
                + quicksum(flow_c[c, s] for c, (i, j) in enumerate(cand_edges) if j == b_) \
                - quicksum(flow_c[c, s] for c, (i, j) in enumerate(cand_edges) if i == b_)
            local_gen = quicksum(gen[g, s] for g in G if int(gen_bus[g]) == b_)
            m.addCons(local_gen + inflow + shed[b_, s] == float(demand[s, b_]),
                      name=f"balance_{b_}_{s}")

    invest = quicksum(float(invest_cost[c]) * build[c] for c in C)
    operation = quicksum(float(scenario_weight[s]) * (
        quicksum(float(gen_cost[g]) * gen[g, s] for g in G)
        + quicksum(VOLL * shed[b_, s] for b_ in B)
    ) for s in S)
    m.setObjective(invest + operation, "minimize")

    m.data = dict(build=build, gen=gen, shed=shed, scale=scale, dims=(nB, nE, nC, nS))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
