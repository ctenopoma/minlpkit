"""順序依存の段取り時間を考慮したフローショップスケジューリング問題 (SDST Flowshop)

複数種類の製品（ジョブ）を複数の連続する工程（マシン）で処理するフローショップにおいて、
同一マシン上で製品を切り替える際に発生する「順序依存の段取り時間 (Sequence-Dependent Setup Time)」を考慮し、
全ジョブの総完了時間（メイクスパン）を最小化するスケジュールを求めます。
"""

from pyscipopt import Model, quicksum

def build_model() -> Model:
    model = Model("Sequence_Dependent_Flowshop")

    # ---- データ設定 ----
    JOBS = ["J1", "J2", "J3", "J4"]
    MACHINES = ["M1", "M2", "M3"]

    # 各ジョブのマシン上での処理時間 P[job, machine]
    P = {
        ("J1", "M1"): 3.0, ("J1", "M2"): 4.0, ("J1", "M3"): 2.0,
        ("J2", "M1"): 2.0, ("J2", "M2"): 1.0, ("J2", "M3"): 4.0,
        ("J3", "M1"): 4.0, ("J3", "M2"): 3.0, ("J3", "M3"): 3.0,
        ("J4", "M1"): 1.0, ("J4", "M2"): 5.0, ("J4", "M3"): 2.0,
    }

    # 順序依存の段取り時間 S[from_job, to_job, machine]
    # ジョブ切り替え時の段取り時間（ダミージョブ "0" は最初および最後を表す）
    ALL_JOBS = ["0"] + JOBS
    S = {}
    for m in MACHINES:
        for j1 in ALL_JOBS:
            for j2 in ALL_JOBS:
                if j1 == j2:
                    S[j1, j2, m] = 0.0
                elif j1 == "0" or j2 == "0":
                    S[j1, j2, m] = 1.0  # 初期段取り・終了段取り
                else:
                    # 製品固有の切り替え時間
                    if j1 == "J1" and j2 == "J2": S[j1, j2, m] = 2.0
                    elif j1 == "J2" and j2 == "J1": S[j1, j2, m] = 3.5
                    elif j1 == "J3" and j2 == "J4": S[j1, j2, m] = 1.5
                    elif j1 == "J4" and j2 == "J3": S[j1, j2, m] = 2.0
                    else: S[j1, j2, m] = 2.5  # デフォルトの切り替え時間

    # 十分大きな正数 Big-M
    BIG_M = 100.0

    # ---- 変数定義 ----
    # x[j, k, m]: マシンm上でジョブjの直後にジョブkが処理されるとき1 (バイナリ)
    x = {}
    for m in MACHINES:
        for j in ALL_JOBS:
            for k in ALL_JOBS:
                if j != k:
                    x[j, k, m] = model.addVar(vtype="B", name=f"x_{j}_{k}_{m}")

    # s[j, m]: マシンmにおけるジョブjの開始時間 (連続)
    s = {}
    for j in JOBS:
        for m in MACHINES:
            s[j, m] = model.addVar(vtype="C", lb=0.0, name=f"s_{j}_{m}")

    # Cmax: メイクスパン (連続)
    cmax = model.addVar(vtype="C", lb=0.0, name="cmax")

    # ---- 制約定義 ----
    for m in MACHINES:
        # 1. 各ジョブjは各マシンmで一度だけ「後続」をもつ
        for j in JOBS:
            model.addCons(
                quicksum(x[j, k, m] for k in ALL_JOBS if k != j) == 1,
                name=f"out_flow_{j}_{m}"
            )
        # 2. 各ジョブjは各マシンmで一度だけ「先行」をもつ
        for j in JOBS:
            model.addCons(
                quicksum(x[k, j, m] for k in ALL_JOBS if k != j) == 1,
                name=f"in_flow_{j}_{m}"
            )
        # 3. ダミージョブ "0" からの出発および "0" への到着は一度だけ
        model.addCons(
            quicksum(x["0", k, m] for k in JOBS) == 1,
            name=f"dummy_start_{m}"
        )
        model.addCons(
            quicksum(x[j, "0", m] for j in JOBS) == 1,
            name=f"dummy_end_{m}"
        )

    # 4. 開始時間の順序制約 (マシン内の先行・後続関係)
    for m in MACHINES:
        for j in JOBS:
            for k in JOBS:
                if j != k:
                    # x[j,k,m] = 1 のとき, s[k,m] >= s[j,m] + P[j,m] + S[j,k,m]
                    model.addCons(
                        s[k, m] >= s[j, m] + P[j, m] + S[j, k, m] - BIG_M * (1 - x[j, k, m]),
                        name=f"seq_time_{j}_{k}_{m}"
                    )

    # 5. ジョブのマシン間先行制約 (フローショップ構造)
    for j in JOBS:
        for idx in range(len(MACHINES) - 1):
            m1 = MACHINES[idx]
            m2 = MACHINES[idx+1]
            # マシンm2での開始は、マシンm1での処理完了後
            model.addCons(
                s[j, m2] >= s[j, m1] + P[j, m1],
                name=f"flow_constraint_{j}_{m1}_{m2}"
            )

    # 6. メイクスパンの定義 (最後のマシンの完了時間)
    last_m = MACHINES[-1]
    for j in JOBS:
        model.addCons(
            cmax >= s[j, last_m] + P[j, last_m] + S[j, "0", last_m],
            name=f"makespan_def_{j}"
        )

    # 目的関数
    model.setObjective(cmax, "minimize")

    model.data = {"x": x, "s": s, "cmax": cmax}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        print(f"Optimal Makespan (Cmax): {model.getObjVal():.2f}")
        x = model.data["x"]
        s = model.data["s"]
        cmax = model.data["cmax"]

        # 各マシンのジョブ順序を復元して表示
        JOBS = ["J1", "J2", "J3", "J4"]
        MACHINES = ["M1", "M2", "M3"]
        print("\n--- Sequence per Machine ---")
        for m in MACHINES:
            sequence = []
            curr = "0"
            while True:
                # 次のジョブを探す
                next_j = None
                for k in ["0"] + JOBS:
                    if curr != k:
                        if model.getVal(x[curr, k, m]) > 0.5:
                            next_j = k
                            break
                if next_j is None or next_j == "0":
                    break
                sequence.append(next_j)
                curr = next_j
            
            print(f"Machine {m}: " + " -> ".join(sequence))
            for j in sequence:
                start_v = model.getVal(s[j, m])
                print(f"  {j}: starts at {start_v:.1f}")

if __name__ == "__main__":
    main()
