"""小売クリアランス値引き時期決定 (Retail Clearance Markdown)

事業ストーリー
--------------
小売チェーンの「在庫消化担当」が、シーズン末在庫を持つ複数商品カテゴリについて、
数週間の販売期間中いつ・どれだけ値引き幅を投入するかを決める意思決定である。
値引きは深いほど需要が伸びるがマージンを圧迫し、かつ一度値引きを開始したカテゴリは
翌週以降も値引き幅を維持または拡大する(値引き幅を戻すと顧客の信頼を損なうため)という
現場の運用ルールがある。担当者は各カテゴリについて週ごとの値引き幅(複数段階の中から
選択)を決め、在庫を計画期間内に売り切りつつ、値引きによる粗利減少を最小化する。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_category=2, n_week=3, n_level=2),
    "default": dict(n_category=3, n_week=4, n_level=3),
    "large": dict(n_category=4, n_week=5, n_level=3),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_category, n_week, n_level = cfg["n_category"], cfg["n_week"], cfg["n_level"]
    categories, weeks, levels = range(n_category), range(n_week), range(n_level)

    # 値引き幅レベル(0=値引きなし, 1=浅い, 2=深い, ...): 深いほど需要押し上げ効果が大きい
    demand_lift = {lv: 1.0 + 0.35 * lv for lv in levels}
    margin_loss = {lv: 0.08 * lv for lv in levels}  # 値引き幅による粗利率低下

    base_demand = {c: 80 + 20 * c for c in categories}
    base_margin = {c: 25 + 5 * c for c in categories}
    # 在庫は「値引きなしを続けた場合の総需要」に15%の余裕を載せた水準に設定する。
    # これにより最小(値引きゼロ)ケースでも在庫上限を超えず、かつクリアランス目標
    # (在庫の85%)は達成可能な範囲に収まる(値引き幅の選択次第で在庫消化速度を調整)。
    inventory = {c: round(n_week * base_demand[c] * 1.15) for c in categories}

    model = Model("Retail_Clearance_Markdown")

    # 週cごと・レベルごとの値引き選択(排他的1本化)
    level_sel = {(c, t, lv): model.addVar(vtype="B", name=f"lvl_{c}_{t}_{lv}")
                 for c in categories for t in weeks for lv in levels}
    sold = {(c, t): model.addVar(vtype="C", lb=0, name=f"sold_{c}_{t}") for c in categories for t in weeks}
    level_idx = {(c, t): model.addVar(vtype="I", lb=0, ub=n_level - 1, name=f"lvlidx_{c}_{t}")
                 for c in categories for t in weeks}

    for c in categories:
        for t in weeks:
            model.addCons(quicksum(level_sel[c, t, lv] for lv in levels) == 1, name=f"level_choice_{c}_{t}")
            model.addCons(
                level_idx[c, t] == quicksum(lv * level_sel[c, t, lv] for lv in levels), name=f"level_idx_{c}_{t}")
            model.addCons(
                sold[c, t] == base_demand[c] * quicksum(demand_lift[lv] * level_sel[c, t, lv] for lv in levels),
                name=f"sold_def_{c}_{t}")
        # 在庫制約: 全週の販売合計が在庫を超えない
        model.addCons(quicksum(sold[c, t] for t in weeks) <= inventory[c], name=f"inventory_{c}")
        # クリアランス要件: 期末までに在庫の大半を売り切る
        model.addCons(quicksum(sold[c, t] for t in weeks) >= 0.85 * inventory[c], name=f"clearance_target_{c}")

    for c in categories:
        for t in range(1, n_week):
            # 値引き幅レベルは週を追うごとに単調非減少(戻し値引き禁止)
            model.addCons(level_idx[c, t] >= level_idx[c, t - 1], name=f"monotone_{c}_{t}")

    # 値引き損失額は「販売数量(=需要押し上げ後の量)×粗利率低下」だが、sold自体が
    # level_sel の線形結合で定義されているため、係数を事前展開して level_sel の線形式のまま保つ
    # (sold * level_sel の双線形項を作らない = SCIPの非線形目的関数制限を回避)
    total_margin_loss = quicksum(
        base_demand[c] * demand_lift[lv] * margin_loss[lv] * base_margin[c] * level_sel[c, t, lv]
        for c in categories for t in weeks for lv in levels)
    model.setObjective(total_margin_loss, "minimize")
    model.data = {"level_sel": level_sel, "sold": sold, "dims": (n_category, n_week, n_level)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Margin Loss:", m.getObjVal())
