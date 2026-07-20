"""多期間サプライチェーンネットワーク計画 (Multi-period Supply Chain Network Planning)

サプライチェーン計画担当者が、複数期間・複数拠点(工場→配送センター→顧客)にわたる
出荷量と在庫量を同時に決める意思決定である。各期の在庫バランス制約(前期在庫+入荷-出荷=需要)
により、当期の輸送判断が翌期以降の在庫コストに波及するため単純な期別最適化では捉えられない。
さらに配送センターごとに輸送ロットを大型トラック単位でしか送れない(固定容量×整数台数)という
現実的な制約を加え、輸送費と保管費のトレードオフ(まとめ買いで輸送費を節約するか、
在庫費用を避けて都度輸送するか)を表現する。
"""

from pyscipopt import Model, quicksum

TRUCK_CAPACITY = 30.0
TRUCK_COST = 80.0


def build_model():
    model = Model("SupplyChain_MultiPeriod")
    T = 4
    DCS = ["DC1", "DC2", "DC3"]
    demand = {
        ("DC1", 0): 20, ("DC1", 1): 22, ("DC1", 2): 25, ("DC1", 3): 28,
        ("DC2", 0): 15, ("DC2", 1): 18, ("DC2", 2): 16, ("DC2", 3): 20,
        ("DC3", 0): 10, ("DC3", 1): 12, ("DC3", 2): 14, ("DC3", 3): 15,
    }
    unit_transport_cost = {"DC1": 10.0, "DC2": 12.0, "DC3": 9.0}
    holding_cost = {"DC1": 2.0, "DC2": 2.5, "DC3": 1.8}
    init_inv = {"DC1": 5.0, "DC2": 3.0, "DC3": 4.0}

    x = {(d, t): model.addVar(vtype="C", lb=0, name=f"x_{d}_{t}") for d in DCS for t in range(T)}
    s = {(d, t): model.addVar(vtype="C", lb=0, name=f"s_{d}_{t}") for d in DCS for t in range(T)}
    trucks = {(d, t): model.addVar(vtype="I", lb=0, name=f"trucks_{d}_{t}") for d in DCS for t in range(T)}

    for d in DCS:
        for t in range(T):
            prev_inv = init_inv[d] if t == 0 else s[d, t - 1]
            model.addCons(prev_inv + x[d, t] - s[d, t] == demand[d, t], name=f"bal_{d}_{t}")
            # 輸送量はトラック台数(整数)×積載容量でしか運べない
            model.addCons(x[d, t] <= TRUCK_CAPACITY * trucks[d, t], name=f"truck_cap_{d}_{t}")

    model.setObjective(
        quicksum(
            unit_transport_cost[d] * x[d, t] + holding_cost[d] * s[d, t] + TRUCK_COST * trucks[d, t]
            for d in DCS for t in range(T)
        ),
        "minimize",
    )
    model.data = {"x": x, "s": s, "trucks": trucks}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Cost:", m.getObjVal())
