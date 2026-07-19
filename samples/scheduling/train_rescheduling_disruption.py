"""列車運行の障害時再スケジュール (Rescheduling under Disruption) モデル (MILP)

事故や災害などによる急なダイヤ乱れ（特定区間での速度制限、駅での出発遅延など）が発生した際に、
複数列車の運行順序の変更（退避・追い越し）、駅での発着時刻のシフト、
および被害が大きい場合の運休（Cancellation）判断を同時に最適化する運転整理モデルです。
ジョブショップスケジューリングの拡張として定式化し、
「基準ダイヤからのズレの総和」と「運休ペナルティ」を最小化します。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Train_Rescheduling_Disruption")

    # ---- データ設定 ----
    TRAINS = ["T1", "T2", "T3"]
    STATIONS = [0, 1, 2, 3]  # 4駅、3区間

    # 基準ダイヤ (Planned Schedule) [分]
    # (T1: 普通, T2: 特急, T3: 普通)
    PLAN_A = {
        "T1": {0: 0, 1: 15, 2: 30, 3: 45},
        "T2": {0: 10, 1: 20, 2: 30, 3: 40}, # T2は速い
        "T3": {0: 30, 1: 45, 2: 60, 3: 75}
    }
    PLAN_D = {
        "T1": {0: 2, 1: 17, 2: 32, 3: 45},
        "T2": {0: 12, 1: 22, 2: 32, 3: 40},
        "T3": {0: 32, 1: 47, 2: 62, 3: 75}
    }

    # 駅間最小走行時間 (平常時)
    MIN_RUN_TIME = {
        "T1": {0: 13, 1: 13, 2: 13},
        "T2": {0: 8, 1: 8, 2: 8},
        "T3": {0: 13, 1: 13, 2: 13}
    }

    # 最小停車時間
    MIN_STOP_TIME = 1.0

    # 障害のシナリオ (Disruption Scenario)
    # 例: 区間1 (駅1->駅2) で障害発生、走行時間が大幅増
    DISRUPT_RUN_TIME = {
        ("T1", 1): 25,
        ("T2", 1): 20,
        ("T3", 1): 25
    }

    # 単線区間の制約を想定 (列車の追い越しは駅でのみ可能)
    # 同一区間内に同時に存在してはならない、または間隔(ヘッドウェイ)をあける
    HEADWAY = 3.0 
    BIG_M = 1000.0

    # 運休ペナルティ
    CANCEL_PENALTY = 500.0
    # 遅延ペナルティ係数 (特急T2は重くする)
    WEIGHT = {"T1": 1.0, "T2": 3.0, "T3": 1.0}

    # ---- 変数定義 ----
    # a[tr, s]: 到着時刻, d[tr, s]: 出発時刻
    a = {}
    d = {}
    for tr in TRAINS:
        for s in STATIONS:
            a[tr, s] = model.addVar(vtype="C", lb=PLAN_A[tr][s], ub=PLAN_A[tr][s]+120, name=f"a_{tr}_{s}")
            if s < STATIONS[-1]:
                d[tr, s] = model.addVar(vtype="C", lb=PLAN_D[tr][s], ub=PLAN_D[tr][s]+120, name=f"d_{tr}_{s}")

    # y[tr]: 運休フラグ (1: 運休, 0: 運行)
    y = {}
    for tr in TRAINS:
        y[tr] = model.addVar(vtype="B", name=f"y_{tr}")

    # x[tr1, tr2, s]: 順序変数 (駅sにおいて、tr1がtr2より先に出発するなら1)
    x_order = {}
    for i, tr1 in enumerate(TRAINS):
        for j, tr2 in enumerate(TRAINS):
            if i < j:
                for s in STATIONS[:-1]:
                    x_order[tr1, tr2, s] = model.addVar(vtype="B", name=f"x_{tr1}_{tr2}_{s}")

    # 遅延量
    delay = {}
    for tr in TRAINS:
        delay[tr] = model.addVar(vtype="C", lb=0.0, name=f"delay_{tr}")

    # ---- 制約定義 ----
    for tr in TRAINS:
        # 遅延の定義 (終点での到着遅れ)
        # 運休した場合は遅延を計算しない（緩和）
        model.addCons(delay[tr] >= a[tr, STATIONS[-1]] - PLAN_A[tr][STATIONS[-1]] - BIG_M * y[tr])

        for s in STATIONS[:-1]:
            # 最小停車時間
            model.addCons(d[tr, s] - a[tr, s] >= MIN_STOP_TIME - BIG_M * y[tr])
            
            # 走行時間 (障害があれば上書き)
            rt = DISRUPT_RUN_TIME.get((tr, s), MIN_RUN_TIME[tr][s])
            model.addCons(a[tr, s+1] - d[tr, s] >= rt - BIG_M * y[tr])

    # 競合制約 (ヘッドウェイ、追い越し不可制約)
    # 簡易化: 同一区間 (s -> s+1) に入る順序と出る順序は同じ (駅間で追い越し不可)
    for i, tr1 in enumerate(TRAINS):
        for j, tr2 in enumerate(TRAINS):
            if i < j:
                for s in STATIONS[:-1]:
                    # tr1が先に出るケース
                    # d[tr2, s] >= d[tr1, s] + HEADWAY
                    model.addCons(d[tr2, s] >= d[tr1, s] + HEADWAY - BIG_M * (1 - x_order[tr1, tr2, s]) - BIG_M * y[tr1] - BIG_M * y[tr2])
                    # 駅間で追い越せないため、到着順も同じになる
                    model.addCons(a[tr2, s+1] >= a[tr1, s+1] + HEADWAY - BIG_M * (1 - x_order[tr1, tr2, s]) - BIG_M * y[tr1] - BIG_M * y[tr2])

                    # tr2が先に出るケース
                    model.addCons(d[tr1, s] >= d[tr2, s] + HEADWAY - BIG_M * x_order[tr1, tr2, s] - BIG_M * y[tr1] - BIG_M * y[tr2])
                    model.addCons(a[tr1, s+1] >= a[tr2, s+1] + HEADWAY - BIG_M * x_order[tr1, tr2, s] - BIG_M * y[tr1] - BIG_M * y[tr2])

    # ---- 目的関数 ----
    # 重み付き総遅延 + 運休ペナルティ
    obj = quicksum(WEIGHT[tr] * delay[tr] for tr in TRAINS) + quicksum(CANCEL_PENALTY * y[tr] for tr in TRAINS)
    model.setObjective(obj, "minimize")
    
    return model

if __name__ == "__main__":
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print(f"Optimal Objective: {m.getObjVal():.2f}")
        for tr in ["T1", "T2", "T3"]:
            y_val = m.getVal(m.getVars()[m.getVars().index([v for v in m.getVars() if v.name == f"y_{tr}"][0])])
            if y_val > 0.5:
                print(f"Train {tr}: CANCELLED")
            else:
                delay_val = m.getVal(m.getVars()[m.getVars().index([v for v in m.getVars() if v.name == f"delay_{tr}"][0])])
                print(f"Train {tr}: Delay = {delay_val:.2f} min")
