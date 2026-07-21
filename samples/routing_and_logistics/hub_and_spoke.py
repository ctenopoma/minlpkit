"""物流ネットワークのハブ立地・スポーク割当計画 (Hub and Spoke Network Design)

事業ストーリー
--------------
物流ネットワーク設計担当者が、複数の拠点候補の中からハブ(集約中継拠点)をいくつ・どこに
開設するかと、各拠点(スポーク)をどのハブに割り当てるかを同時に決める。ハブ拠点は
集約効果でハブ間輸送コストが割安になる一方、開設固定費とハブ容量(処理能力)の制約があるため、
拠点数(開設候補数の上限)と各拠点発の物量をどのハブ経由で流すかを合わせて最適化する必要がある
(古典的な p-ハブ・メディアン問題の簡略版)。
"""

from pyscipopt import Model, quicksum

NODES = ["N1", "N2", "N3", "N4"]
P_MAX = 2                          # 開設できるハブ数の上限
HUB_FIXED_COST = {"N1": 3000, "N2": 2500, "N3": 2800, "N4": 2200}
HUB_CAP = {"N1": 200, "N2": 150, "N3": 180, "N4": 130}
OUT_FLOW = {"N1": 60, "N2": 45, "N3": 55, "N4": 40}   # 各拠点が発送する物量
# 拠点→ハブの引込コスト(距離に応じた単価)
COLLECT_COST = {
    ("N1", "N1"): 0, ("N1", "N2"): 8, ("N1", "N3"): 6, ("N1", "N4"): 10,
    ("N2", "N1"): 8, ("N2", "N2"): 0, ("N2", "N3"): 7, ("N2", "N4"): 9,
    ("N3", "N1"): 6, ("N3", "N2"): 7, ("N3", "N3"): 0, ("N3", "N4"): 5,
    ("N4", "N1"): 10, ("N4", "N2"): 9, ("N4", "N3"): 5, ("N4", "N4"): 0,
}
ALPHA_BACKBONE = 3.0               # ハブ経由の幹線輸送コスト(規模の経済適用後の平均単価)


def build_model():
    model = Model("Hub_And_Spoke")
    N = NODES

    h = {k: model.addVar(vtype="B", name=f"h_{k}") for k in N}
    assign = {(i, k): model.addVar(vtype="B", name=f"assign_{i}_{k}") for i in N for k in N}
    hub_flow = {k: model.addVar(vtype="C", lb=0, name=f"hub_flow_{k}") for k in N}

    model.addCons(quicksum(h[k] for k in N) <= P_MAX, "max_hubs")

    for i in N:
        model.addCons(quicksum(assign[i, k] for k in N) == 1, f"assign_one_{i}")
    for k in N:
        model.addCons(quicksum(assign[i, k] for i in N) <= len(N) * h[k], f"assign_link_{k}")

    for k in N:
        model.addCons(hub_flow[k] == quicksum(OUT_FLOW[i] * assign[i, k] for i in N),
                      f"hub_flow_def_{k}")
        model.addCons(hub_flow[k] <= HUB_CAP[k] * h[k], f"hub_capacity_{k}")

    fixed = quicksum(HUB_FIXED_COST[k] * h[k] for k in N)
    collect = quicksum(COLLECT_COST[i, k] * assign[i, k] for i in N for k in N)
    backbone = ALPHA_BACKBONE * quicksum(hub_flow[k] for k in N)
    model.setObjective(fixed + collect + backbone, "minimize")

    model.data = {"h": h, "assign": assign, "hub_flow": hub_flow}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
