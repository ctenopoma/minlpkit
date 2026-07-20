"""小売シーズン値引き価格最適化 (Price Optimization with Markdown)

事業ストーリー
--------------
小売チェーンの「プライシング担当」が、季節商品(アパレル等)の複数店舗・複数週にわたる
値引き価格を決める意思決定である。各週の需要は価格弾力性(価格が下がるほど需要が増える
線形近似)に従うため、売上 = 価格×需要 は価格の二次関数(非線形)になる。担当者は
在庫制約(各店舗に配分された初期在庫を売り切る)と、価格の週次単調性(値引きは進行方向
のみ、途中で値上げに戻さない)という業務ルールの下で、総収益を最大化する価格経路を
店舗ごとに設計する。値上げ復帰を禁じるのは、顧客の値引き期待を裏切らないための
小売現場の暗黙ルールを整数変数(値下げ実施フラグ)で明示化したものである。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_store=2, n_week=3),
    "default": dict(n_store=3, n_week=4),
    "large": dict(n_store=4, n_week=5),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_store, n_week = cfg["n_store"], cfg["n_week"]
    stores = range(n_store)
    weeks = range(n_week)

    # 店舗ごとの初期在庫・需要曲線パラメータ(店舗によって商圏規模が異なる)
    inventory = {s: 200 + 40 * s for s in stores}
    demand_a = {s: 120 + 15 * s for s in stores}  # 切片(価格0での潜在需要)
    demand_b = {s: 2.0 for s in stores}  # 価格弾力性係数
    price_min, price_max = 10.0, 50.0

    model = Model("Markdown_Price_Optimization")

    price = {(s, t): model.addVar(vtype="C", lb=price_min, ub=price_max, name=f"price_{s}_{t}")
             for s in stores for t in weeks}
    demand = {(s, t): model.addVar(vtype="C", lb=0, name=f"demand_{s}_{t}")
              for s in stores for t in weeks}
    revenue = {(s, t): model.addVar(vtype="C", lb=0, name=f"revenue_{s}_{t}")
               for s in stores for t in weeks}
    # 値下げ実施フラグ: 一度下げたら翌週以降も価格は非増加(値上げ復帰の禁止)
    markdown = {(s, t): model.addVar(vtype="B", name=f"md_{s}_{t}") for s in stores for t in range(1, n_week)}

    for s in stores:
        for t in weeks:
            model.addCons(demand[s, t] == demand_a[s] - demand_b[s] * price[s, t], name=f"demand_curve_{s}_{t}")
            model.addCons(revenue[s, t] == price[s, t] * demand[s, t], name=f"revenue_def_{s}_{t}")
        # 在庫制約: 全週の需要合計が初期在庫を超えない
        model.addCons(quicksum(demand[s, t] for t in weeks) <= inventory[s], name=f"inventory_{s}")

    for s in stores:
        for t in range(1, n_week):
            # 値下げフラグが立った週は前週以下の価格、立たなければ前週と同額
            model.addCons(price[s, t] <= price[s, t - 1], name=f"monotone_{s}_{t}")
            model.addCons(price[s, t] >= price[s, t - 1] - (price_max - price_min) * markdown[s, t],
                          name=f"markdown_link_{s}_{t}")
        # 値下げ回数の上限(頻繁な値下げはブランド毀損につながるため業務ルールで制限)
        model.addCons(quicksum(markdown[s, t] for t in range(1, n_week)) <= 2, name=f"markdown_limit_{s}")

    model.setObjective(quicksum(revenue[s, t] for s in stores for t in weeks), "maximize")
    model.data = {"price": price, "demand": demand, "revenue": revenue, "markdown": markdown,
                  "dims": (n_store, n_week)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Max Revenue:", m.getObjVal())
