"""化学プラントのバッチプロセススケジューリング (STNモデル)

State-Task Network (STN)モデルに基づき、原料から中間体を経て最終製品を生産する
多品種バッチプロセスのスケジュールを最適化します。
装置の容量制限、タスク処理時間、在庫制限、および装置の排他制御（同一時刻に1つのタスクのみ実行可能）
を考慮した混合整数線形計画法 (MILP) モデルです。

定式化の参照:
Kondili, E., Pantelides, C. C., & Sargent, R. W. H. (1993).
A general algorithm for the short-term scheduling of batch operations—I. MILP formulation.
Computers & Chemical Engineering, 17(2), 211-227.
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("STN_Batch_Scheduling")

    # ---- データ設定 ----
    # タイムホライズン
    T = 12  # 時刻ステップ 0 ~ 12
    TIME_STEPS = list(range(T + 1))

    # 状態 (States)
    STATES = {
        "FeedA":    {"initial": 1000.0, "capacity": 1000.0, "price": 0.0},
        "FeedB":    {"initial": 1000.0, "capacity": 1000.0, "price": 0.0},
        "FeedC":    {"initial": 1000.0, "capacity": 1000.0, "price": 0.0},
        "IntAB":    {"initial": 0.0,    "capacity": 100.0,  "price": 0.0},
        "IntBC":    {"initial": 0.0,    "capacity": 100.0,  "price": 0.0},
        "Product1": {"initial": 0.0,    "capacity": 500.0,  "price": 10.0},
        "Product2": {"initial": 0.0,    "capacity": 500.0,  "price": 15.0},
    }

    # タスク (Tasks)
    TASKS = {
        "ReactAB": {"duration": 2, "inputs": {"FeedA": 0.5, "FeedB": 0.5}, "outputs": {"IntAB": 1.0}},
        "ReactBC": {"duration": 2, "inputs": {"FeedB": 0.4, "FeedC": 0.6}, "outputs": {"IntBC": 1.0}},
        "Purify1": {"duration": 1, "inputs": {"IntAB": 0.9},             "outputs": {"Product1": 0.9}},
        "Purify2": {"duration": 2, "inputs": {"IntBC": 0.8},             "outputs": {"Product2": 0.8}},
    }

    # 装置 (Units)
    UNITS = {
        "Reactor1": {"capacity_min": 10.0, "capacity_max": 50.0,  "tasks": ["ReactAB", "ReactBC"]},
        "Reactor2": {"capacity_min": 15.0, "capacity_max": 80.0,  "tasks": ["ReactAB"]},
        "Still":    {"capacity_min": 5.0,  "capacity_max": 40.0,  "tasks": ["Purify1", "Purify2"]},
    }

    # タスクと装置の対応マップ
    units_for_task = {i: [j for j, ud in UNITS.items() if i in ud["tasks"]] for i in TASKS}

    # ---- 変数定義 ----
    # w[i, j, t]: 時刻tに装置jでタスクiが開始されたら1 (バイナリ)
    w = {}
    # b[i, j, t]: 時刻tに装置jで開始されるタスクiのバッチサイズ (連続)
    b = {}
    for i in TASKS:
        for j in units_for_task[i]:
            for t in TIME_STEPS:
                w[i, j, t] = model.addVar(vtype="B", name=f"w_{i}_{j}_{t}")
                b[i, j, t] = model.addVar(vtype="C", lb=0.0, name=f"b_{i}_{j}_{t}")

    # s[s, t]: 時刻t終了時点での状態sの在庫量 (連続)
    s = {}
    for st in STATES:
        for t in TIME_STEPS:
            s[st, t] = model.addVar(vtype="C", lb=0.0, ub=STATES[st]["capacity"], name=f"s_{st}_{t}")

    # ---- 制約定義 ----
    # 1. 初期在庫の設定
    for st, sd in STATES.items():
        model.addCons(s[st, 0] == sd["initial"], name=f"init_stock_{st}")

    # 2. 装置の排他制御・利用可能制約
    for j, ud in UNITS.items():
        for t in TIME_STEPS:
            active_tasks = []
            for i in ud["tasks"]:
                duration = TASKS[i]["duration"]
                for theta in range(max(0, t - duration + 1), t + 1):
                    if (i, j, theta) in w:
                        active_tasks.append(w[i, j, theta])
            model.addCons(quicksum(active_tasks) <= 1, name=f"unit_occupancy_{j}_{t}")

    # 3. バッチ容量制限
    for i in TASKS:
        for j in units_for_task[i]:
            cap_min = UNITS[j]["capacity_min"]
            cap_max = UNITS[j]["capacity_max"]
            for t in TIME_STEPS:
                model.addCons(b[i, j, t] >= cap_min * w[i, j, t], name=f"cap_min_{i}_{j}_{t}")
                model.addCons(b[i, j, t] <= cap_max * w[i, j, t], name=f"cap_max_{i}_{j}_{t}")

    # 4. 在庫バランス制約
    for t in TIME_STEPS[1:]:
        for st in STATES:
            consumed = []
            for i, td in TASKS.items():
                if st in td["inputs"]:
                    ratio = td["inputs"][st]
                    for j in units_for_task[i]:
                        consumed.append(ratio * b[i, j, t])

            produced = []
            for i, td in TASKS.items():
                if st in td["outputs"]:
                    duration = td["duration"]
                    if t >= duration:
                        ratio = td["outputs"][st]
                        for j in units_for_task[i]:
                            produced.append(ratio * b[i, j, t - duration])

            model.addCons(
                s[st, t] == s[st, t - 1] + quicksum(produced) - quicksum(consumed),
                name=f"stock_balance_{st}_{t}"
            )

    # ---- 目的関数 ----
    revenue = quicksum(s[st, T] * sd["price"] for st, sd in STATES.items() if sd["price"] > 0)
    model.setObjective(revenue, "maximize")

    model.data = {"w": w, "b": b, "s": s}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Profit: {model.getObjVal():.2f}")
        w = model.data["w"]
        b = model.data["b"]
        s = model.data["s"]

        print("\n--- Production Schedule ---")
        for (i, j, t), val in w.items():
            w_val = model.getVal(val)
            if w_val > 0.5:
                b_val = model.getVal(b[i, j, t])
                print(f"Time {t:2d}: Unit {j:8s} starts Task {i:8s} (Batch Size: {b_val:.1f})")

        print("\n--- Final Inventory levels ---")
        for st in ["FeedA", "FeedB", "FeedC", "IntAB", "IntBC", "Product1", "Product2"]:
            final_stock = model.getVal(s[st, 12])
            print(f"  {st:10s}: {final_stock:.1f}")

if __name__ == "__main__":
    main()
