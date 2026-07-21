"""多品種サプライチェーン計画 (Multi-commodity Supply Chain Planning)

事業ストーリー
--------------
複数拠点(工場・倉庫)を持つメーカーの「サプライチェーン計画担当」が、複数品目を
複数の供給拠点から複数の需要拠点(顧客・DC)へどう配分するかを決める意思決定である。
各供給拠点には品目ごとの生産・出荷能力があり、各需要拠点には品目ごとの最低充足すべき
需要量がある。輸送には拠点間のリンクごとに単価が異なり、遠距離輸送ほどコストが高い。
一部の拠点間リンクは新規開設が必要(固定の開設コストが発生する)であり、開設しない
限り物流を流せない。計画担当は、各拠点の能力制約と需要充足制約を満たしながら、
輸送変動費とリンク開設固定費の合計を最小化する配分・ネットワーク構成を決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_commodity=2, n_supply=2, n_demand=2),
    "default": dict(n_commodity=3, n_supply=3, n_demand=3),
    "large": dict(n_commodity=4, n_supply=3, n_demand=4),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_commodity, n_supply, n_demand = cfg["n_commodity"], cfg["n_supply"], cfg["n_demand"]
    commodities, supplies, demands = range(n_commodity), range(n_supply), range(n_demand)

    unit_cost = {(c, i, j): 4 + ((c * 5 + i * 3 + j * 2) % 6) for c in commodities for i in supplies for j in demands}
    link_fixed_cost = {(i, j): 80 + 15 * ((i + j) % 4) for i in supplies for j in demands}
    supply_capacity = {(c, i): 60 + 10 * ((c + i) % 3) for c in commodities for i in supplies}
    demand_req = {(c, j): 30 + 8 * ((c + j) % 3) for c in commodities for j in demands}

    model = Model("SupplyChain_MultiCommodity")

    flow = {(c, i, j): model.addVar(vtype="C", lb=0, name=f"flow_{c}_{i}_{j}")
            for c in commodities for i in supplies for j in demands}
    link_open = {(i, j): model.addVar(vtype="B", name=f"open_{i}_{j}") for i in supplies for j in demands}

    big_m = sum(supply_capacity.values())
    for i in supplies:
        for j in demands:
            model.addCons(
                quicksum(flow[c, i, j] for c in commodities) <= big_m * link_open[i, j], name=f"link_gate_{i}_{j}")

    for c in commodities:
        for i in supplies:
            model.addCons(
                quicksum(flow[c, i, j] for j in demands) <= supply_capacity[c, i], name=f"capacity_{c}_{i}")
        for j in demands:
            model.addCons(
                quicksum(flow[c, i, j] for i in supplies) >= demand_req[c, j], name=f"demand_{c}_{j}")

    variable_cost = quicksum(
        unit_cost[c, i, j] * flow[c, i, j] for c in commodities for i in supplies for j in demands)
    fixed_cost = quicksum(link_fixed_cost[i, j] * link_open[i, j] for i in supplies for j in demands)
    model.setObjective(variable_cost + fixed_cost, "minimize")
    model.data = {"flow": flow, "link_open": link_open, "dims": (n_commodity, n_supply, n_demand)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
