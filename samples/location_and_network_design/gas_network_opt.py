"""天然ガス配送網の圧力・バイパス投資計画 (Gas Network Optimization - MINLP)

事業ストーリー
--------------
ガス配送事業者のネットワーク計画担当者が、水源(コンプレッサ)から中継点を経て需要地へ
ガスを送る直列パイプラインの運転圧力を、季節ごとの需要変動(2期)に対して決める。
パイプライン内の流量と圧力損失の関係は Weymouth式に基づく非線形(流量の2乗が圧力差に比例)
であり、既存の直列経路だけでは繁忙期の需要を満たせない可能性があるため、追加のバイパス管を
建設するかどうか(整数の投資判断、建設すれば両期で使える)を同時に検討する。
"""

from pyscipopt import Model

N_T = 2
K1, K2, K3 = 6.0, 5.0, 3.0     # Weymouth係数(区間ごとの管径・長さに依存)
DEMAND_C = [5.0, 8.0]           # 需要地Cでの需要流量(期別)
BYPASS_CAPEX = 4000.0
BYPASS_M = 20.0                 # バイパス流量の大きさ上限(未建設時は0に縛るbig-M)


def build_model():
    model = Model("Gas_Network_Optimization")
    T = range(N_T)

    pA = {t: model.addVar(vtype="C", lb=10, ub=60, name=f"pA_{t}") for t in T}
    pB = {t: model.addVar(vtype="C", lb=8, ub=55, name=f"pB_{t}") for t in T}
    pC = {t: model.addVar(vtype="C", lb=5, ub=50, name=f"pC_{t}") for t in T}
    flow1 = {t: model.addVar(vtype="C", lb=0, ub=15, name=f"flow1_{t}") for t in T}
    flow2 = {t: model.addVar(vtype="C", lb=0, ub=15, name=f"flow2_{t}") for t in T}
    flow_bp = {t: model.addVar(vtype="C", lb=0, ub=BYPASS_M, name=f"flow_bp_{t}") for t in T}
    build_bypass = model.addVar(vtype="B", name="build_bypass")

    for t in T:
        # Weymouth式: 流量^2 = K * 圧力差(区間A-B, B-C)
        model.addCons(flow1[t] * flow1[t] == K1 * (pA[t] - pB[t]), f"weymouth1_{t}")
        model.addCons(flow2[t] * flow2[t] == K2 * (pB[t] - pC[t]), f"weymouth2_{t}")
        # バイパス管(建設時のみ有効): 流量^2 <= K3 * 圧力差
        model.addCons(flow_bp[t] * flow_bp[t] <= K3 * (pA[t] - pC[t]), f"weymouth_bp_{t}")
        model.addCons(flow_bp[t] <= BYPASS_M * build_bypass, f"bypass_link_{t}")
        # 中継点Bでの質量保存(貯留なし)
        model.addCons(flow1[t] == flow2[t], f"mass_balance_{t}")
        # 需要地Cへの供給充足
        model.addCons(flow2[t] + flow_bp[t] >= DEMAND_C[t], f"demand_{t}")

    compression_cost = sum(pA[t] for t in T)
    model.setObjective(compression_cost + (BYPASS_CAPEX / 1000.0) * build_bypass, "minimize")

    model.data = {"pA": pA, "pB": pB, "pC": pC, "flow1": flow1, "flow2": flow2,
                  "flow_bp": flow_bp, "build_bypass": build_bypass}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Objective:", m.getObjVal())
