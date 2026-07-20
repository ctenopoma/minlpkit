"""鉄道運行系統・線路容量計画 (Railway Line Planning)

事業ストーリー
--------------
鉄道事業者の「運行計画部門」が、複数の運行系統(路線)についてダイヤ改正時の運行頻度
(1時間あたりの本数)を決める意思決定である。各系統は速達型・各停型など列車種別
(サービスクラス)によって停車パターン・所要時間・収益単価が異なり、駅間の共有区間では
複数系統の列車本数の合計が線路容量(閉塞・信号システムが許す最大本数)を超えてはならない。
また車両基地の保有編成数が運行に必要な編成数の上限を規定する。計画部門は、区間別容量と
車両制約の両方を満たしながら、系統・種別ごとの運行頻度を整数本で決定し、輸送収益を
最大化する。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_line=3, n_class=2, n_segment=3),
    "default": dict(n_line=4, n_class=2, n_segment=4),
    "large": dict(n_line=5, n_class=3, n_segment=5),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_line, n_class, n_segment = cfg["n_line"], cfg["n_class"], cfg["n_segment"]
    lines, classes, segments = range(n_line), range(n_class), range(n_segment)

    # 系統×種別が共有区間を使うかどうか(路線構造。速達種別ほど通過区間が広い)
    uses_segment = {(i, c, k): 1 if (k <= (2 + c)) and (k % n_line != i or c == n_class - 1) else 0
                    for i in lines for c in classes for k in segments}
    revenue_per_run = {(i, c): 450 + 60 * c + 20 * i for i in lines for c in classes}
    train_sets_needed = {(i, c): 2 + c for i in lines for c in classes}  # 1本の運行に必要な編成数

    segment_capacity = {k: 18 + 2 * k for k in segments}  # 区間ごとの最大列車本数/時
    fleet_size = 60  # 車両基地の保有編成数上限

    model = Model("Railway_Line_Planning")

    freq = {(i, c): model.addVar(vtype="I", lb=0, ub=10, name=f"freq_{i}_{c}") for i in lines for c in classes}

    for k in segments:
        model.addCons(
            quicksum(uses_segment[i, c, k] * freq[i, c] for i in lines for c in classes) <= segment_capacity[k],
            name=f"segment_capacity_{k}")

    model.addCons(
        quicksum(train_sets_needed[i, c] * freq[i, c] for i in lines for c in classes) <= fleet_size,
        name="fleet_capacity")

    # 各系統は最低限のサービス水準(最少本数)を維持する必要がある
    for i in lines:
        model.addCons(quicksum(freq[i, c] for c in classes) >= 2, name=f"min_service_{i}")

    model.setObjective(
        quicksum(freq[i, c] * revenue_per_run[i, c] for i in lines for c in classes), "maximize")
    model.data = {"freq": freq, "dims": (n_line, n_class, n_segment)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Revenue:", m.getObjVal())
