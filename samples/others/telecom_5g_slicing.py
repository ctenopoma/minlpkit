"""5Gネットワークスライシングリソース割当 (5G Telecom Slicing)

通信事業者のネットワークオペレーションセンターが、基地局ごとに限られた無線帯域を
複数のネットワークスライス(eMBB高速通信・URLLC低遅延・mMTC大量接続などの用途別
仮想ネットワーク)へ複数の時間帯にわたって割り当てる意思決定である。各スライスには
契約で定めた最低保証帯域があり、これを下回るとSLA違反となるため優先的に確保しなければ
ならない。新規スライス契約を受け付けるかどうかは0-1の受諾判断(受諾すると最低保証分の
帯域を必ず確保する義務が生じる)であり、基地局の総容量制約の下で受諾収益を最大化する。
"""

from pyscipopt import Model, quicksum

SLICES = ["eMBB", "URLLC", "mMTC"]
PERIODS = range(3)  # 朝・昼・夜のトラフィック帯

capacity = {0: 100.0, 1: 130.0, 2: 90.0}  # 時間帯ごとの基地局総帯域[Mbps]
min_guaranteed = {"eMBB": 10.0, "URLLC": 5.0, "mMTC": 3.0}
revenue_per_mbps = {"eMBB": 12.0, "URLLC": 20.0, "mMTC": 6.0}
new_contract_bonus = {"eMBB": 50.0, "URLLC": 80.0, "mMTC": 25.0}


def build_model():
    model = Model("Telecom_5G_Slicing")

    accept = {s: model.addVar(vtype="B", name=f"accept_{s}") for s in SLICES}
    bw = {(s, t): model.addVar(vtype="C", lb=0, name=f"bw_{s}_{t}") for s in SLICES for t in PERIODS}

    for t in PERIODS:
        model.addCons(quicksum(bw[s, t] for s in SLICES) <= capacity[t], name=f"total_bandwidth_{t}")

    for s in SLICES:
        for t in PERIODS:
            # 契約を受諾したスライスのみ最低保証帯域を確保する義務を負う
            model.addCons(bw[s, t] >= min_guaranteed[s] * accept[s], name=f"sla_min_{s}_{t}")

    model.setObjective(
        quicksum(revenue_per_mbps[s] * bw[s, t] for s in SLICES for t in PERIODS)
        + quicksum(new_contract_bonus[s] * accept[s] for s in SLICES),
        "maximize",
    )
    model.data = {"accept": accept, "bw": bw}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Revenue:", m.getObjVal())
