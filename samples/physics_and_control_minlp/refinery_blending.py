"""石油精製所におけるブレンドスケジューリング (Refinery Blending / Pooling Problem)

複数の原料（原油や留分）を中間プールタンクに一度貯蔵し、それらを再度ブレンドして
最終製品（ガソリンや軽油など）を製造するプロセス（Pooling Problem）をモデル化します。
ブレンド時の成分混合において、「プールの成分濃度 (連続変数) × 流量 (連続変数)」の
双線形項（Bilinear term）が発生するため、非線形計画法 (NLP/MINLP) になります。
SCIP の空間分枝限定法 (Spatial Branch-and-Bound) を用いて、この非凸非線形問題を厳密求解します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Refinery_Blending_Pooling")

    # ---- データ設定 ----
    # 原料 (Feeds): コスト, 最大供給量, 品質特性 (Octane, RVP)
    FEEDS = {
        "Reformate":   {"cost": 60.0, "avail": 100.0, "quality": {"Octane": 99.0, "RVP": 4.0}},
        "FCC_Naphtha": {"cost": 45.0, "avail": 150.0, "quality": {"Octane": 90.0, "RVP": 8.0}},
        "Alkylate":    {"cost": 70.0, "avail": 70.0,  "quality": {"Octane": 97.0, "RVP": 2.0}},
    }

    # プールタンク (Pools): 容量
    POOLS = {
        "Pool_1": {"capacity": 150.0},
        "Pool_2": {"capacity": 100.0},
    }

    # 製品 (Products): 価格, 需要範囲 (min, max), 品質仕様 (Octaneの下限, RVPの上限)
    PRODUCTS = {
        "Premium": {"price": 95.0, "demand_min": 50.0, "demand_max": 120.0, "spec": {"Octane": 96.0, "RVP": 5.0}},
        "Regular": {"price": 80.0, "demand_min": 80.0, "demand_max": 200.0, "spec": {"Octane": 89.0, "RVP": 6.5}},
    }

    QUALITIES = ["Octane", "RVP"]

    # ---- 変数定義 ----
    # f_fl[f, l]: 原料 f からプール l への流量
    f_fl = {}
    for f in FEEDS:
        for l in POOLS:
            f_fl[f, l] = model.addVar(vtype="C", lb=0.0, ub=min(FEEDS[f]["avail"], POOLS[l]["capacity"]), name=f"f_fl_{f}_{l}")

    # f_fg[f, g]: 原料 f から製品 g への直接流量
    f_fg = {}
    for f in FEEDS:
        for g in PRODUCTS:
            f_fg[f, g] = model.addVar(vtype="C", lb=0.0, ub=min(FEEDS[f]["avail"], PRODUCTS[g]["demand_max"]), name=f"f_fg_{f}_{g}")

    # d_lg[l, g]: プール l から製品 g への流量
    d_lg = {}
    for l in POOLS:
        for g in PRODUCTS:
            d_lg[l, g] = model.addVar(vtype="C", lb=0.0, ub=min(POOLS[l]["capacity"], PRODUCTS[g]["demand_max"]), name=f"d_lg_{l}_{g}")

    # q_lp[l, p]: プール l における品質特性 p の濃度
    # 濃度は、原料の最小値と最大値の範囲内になる
    q_lp = {}
    for l in POOLS:
        for p in QUALITIES:
            q_min = min(fd["quality"][p] for fd in FEEDS.values())
            q_max = max(fd["quality"][p] for fd in FEEDS.values())
            q_lp[l, p] = model.addVar(vtype="C", lb=q_min, ub=q_max, name=f"q_lp_{l}_{p}")

    # v_p[l]: プール l に流入する総量 (中間変数)
    v_p = {}
    for l in POOLS:
        v_p[l] = model.addVar(vtype="C", lb=0.0, ub=POOLS[l]["capacity"], name=f"v_p_{l}")

    # v_g[g]: 製品 g の総製造量 (中間変数)
    v_g = {}
    for g in PRODUCTS:
        v_g[g] = model.addVar(vtype="C", lb=PRODUCTS[g]["demand_min"], ub=PRODUCTS[g]["demand_max"], name=f"v_g_{g}")

    # ---- 制約定義 ----
    # 1. 原料の供給上限制約
    for f, fd in FEEDS.items():
        model.addCons(
            quicksum(f_fl[f, l] for l in POOLS) + quicksum(f_fg[f, g] for g in PRODUCTS) <= fd["avail"],
            name=f"feed_avail_{f}"
        )

    # 2. プール l の流入量定義と容量制限
    for l, pd in POOLS.items():
        model.addCons(
            v_p[l] == quicksum(f_fl[f, l] for f in FEEDS),
            name=f"pool_inflow_def_{l}"
        )
        # プールタンクからの流出量 = 流入量 (定常状態)
        model.addCons(
            v_p[l] == quicksum(d_lg[l, g] for g in PRODUCTS),
            name=f"pool_balance_{l}"
        )

    # 3. プールにおける成分混合バランス (双線形制約)
    # 流入成分量 sum(Q_f * F_fl) == プール濃度 q_lp * 総流入量 v_p
    for l in POOLS:
        for p in QUALITIES:
            model.addCons(
                quicksum(FEEDS[f]["quality"][p] * f_fl[f, l] for f in FEEDS) == q_lp[l, p] * v_p[l],
                name=f"pool_blend_{l}_{p}"
            )

    # 4. 製品 g の総量定義
    for g in PRODUCTS:
        model.addCons(
            v_g[g] == quicksum(f_fg[f, g] for f in FEEDS) + quicksum(d_lg[l, g] for l in POOLS),
            name=f"prod_vol_def_{g}"
        )

    # 5. 製品の品質規格制限 (双線形制約)
    # 製品の成分量 = 直接原料分 + プール経由分
    # Quality specifications: Octane >= premium_spec, RVP <= rvp_spec
    for g, gd in PRODUCTS.items():
        # Octane 下限制約
        octane_total = quicksum(FEEDS[f]["quality"]["Octane"] * f_fg[f, g] for f in FEEDS) + \
                       quicksum(q_lp[l, "Octane"] * d_lg[l, g] for l in POOLS)
        model.addCons(
            octane_total >= gd["spec"]["Octane"] * v_g[g],
            name=f"octane_spec_{g}"
        )
        # RVP 上限制約
        rvp_total = quicksum(FEEDS[f]["quality"]["RVP"] * f_fg[f, g] for f in FEEDS) + \
                    quicksum(q_lp[l, "RVP"] * d_lg[l, g] for l in POOLS)
        model.addCons(
            rvp_total <= gd["spec"]["RVP"] * v_g[g],
            name=f"rvp_spec_{g}"
        )

    # ---- 目的関数 ----
    # 利益 = 製品売上 - 原料コスト
    revenue = quicksum(v_g[g] * pd["price"] for g, pd in PRODUCTS.items())
    cost_feeds = quicksum((quicksum(f_fl[f, l] for l in POOLS) + quicksum(f_fg[f, g] for g in PRODUCTS)) * fd["cost"]
                          for f, fd in FEEDS.items())
    profit = revenue - cost_feeds
    model.setObjective(profit, "maximize")

    model.data = {
        "f_fl": f_fl, "f_fg": f_fg, "d_lg": d_lg,
        "q_lp": q_lp, "v_p": v_p, "v_g": v_g
    }
    return model

def main() -> None:
    model = build_model()
    # 非線形問題のため、SCIPの探索出力を有効にして進捗を見やすくする
    model.optimize()

    status = model.getStatus()
    print(f"\nOptimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Profit: {model.getObjVal():.2f} USD")
        d = model.data

        print("\n--- Product Yields ---")
        for g in ["Premium", "Regular"]:
            vol = model.getVal(d["v_g"][g])
            print(f"  {g:8s}: {vol:.1f} bbl")

        print("\n--- Material Flow Details ---")
        print("  From Raw Feeds directly to Products:")
        for (f, g), val in d["f_fg"].items():
            flow = model.getVal(val)
            if flow > 0.1:
                print(f"    {f:12s} -> {g:8s} : {flow:.1f} bbl")

        print("\n  From Raw Feeds into Intermediate Pools:")
        for (f, l), val in d["f_fl"].items():
            flow = model.getVal(val)
            if flow > 0.1:
                print(f"    {f:12s} -> {l:8s} : {flow:.1f} bbl")

        print("\n  Pool Properties:")
        for l in ["Pool_1", "Pool_2"]:
            vol = model.getVal(d["v_p"][l])
            octane = model.getVal(d["q_lp"][l, "Octane"])
            rvp = model.getVal(d["q_lp"][l, "RVP"])
            print(f"    {l:8s} : Volume = {vol:.1f} bbl, Octane = {octane:.2f}, RVP = {rvp:.2f}")

        print("\n  From Pools to Final Products:")
        for (l, g), val in d["d_lg"].items():
            flow = model.getVal(val)
            if flow > 0.1:
                print(f"    {l:8s} -> {g:8s} : {flow:.1f} bbl")

if __name__ == "__main__":
    main()
