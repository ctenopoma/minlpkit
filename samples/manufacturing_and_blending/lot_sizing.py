"""多期間ロットサイジング問題 (Multi-period Lot Sizing Problem)

事業ストーリー
--------------
消費財メーカーの生産計画担当者が、月次の需要予測をもとに1年間(12か月)の生産
ロットサイズ(いつ・どれだけ生産するか)を決める。生産を開始するたびに段取り替え
(設備の切り替え・治具交換)による固定費用が発生する一方、需要より多く作って
在庫として持ち越すと保管コストがかかる。毎月こまめに少量生産すれば在庫費は
抑えられるが段取り費がかさみ、逆にまとめ生産すれば段取り費は減るが在庫費が
増える、というトレードオフの中で年間コストを最小化する生産計画を立てる。

各制約の業務的意味:
- **在庫バランス**: 各月の期首在庫(前月末在庫)に当月生産量を足し、当月出荷
  (需要)を引いたものが当月末在庫になる(需要を満たしつつ在庫量を正しく追跡する)。
- **生産能力と段取りの連動**: 生産するなら段取り替えを実施しなければならず
  (段取りフラグが立たない限り生産量は0)、1か月あたりの生産量には設備能力上限
  がある。

(元の学術的定義: Wagner-Whitin algorithm (1958) - Dynamic version of the economic lot size model.)
"""

from pyscipopt import Model

def build_model(infeasible=False):
    model = Model("LotSizing")

    # 1年間(12か月)の需要予測(季節変動あり)
    periods = 12
    demand = [20, 50, 10, 40, 30, 60, 45, 35, 55, 25, 15, 40]
    setup_cost = 150
    prod_cost = 5
    hold_cost = 2
    capacity = 60

    # Variables
    x = {} # Production amount
    y = {} # Setup indicator
    s = {} # Inventory level

    for t in range(periods):
        x[t] = model.addVar(vtype="C", lb=0, name=f"prod_{t}")
        y[t] = model.addVar(vtype="B", name=f"setup_{t}")
        s[t] = model.addVar(vtype="C", lb=0, name=f"inv_{t}")

    # Constraints
    for t in range(periods):
        # Inventory balance
        if t == 0:
            model.addCons(x[t] - s[t] == demand[t], name=f"inv_bal_{t}")
        else:
            model.addCons(s[t-1] + x[t] - s[t] == demand[t], name=f"inv_bal_{t}")

        # Capacity and setup constraint
        model.addCons(x[t] <= capacity * y[t], name=f"cap_setup_{t}")

    if infeasible:
        model.addCons(x[0] <= 0, name="inf_constraint")

    # Objective
    model.setObjective(sum(setup_cost * y[t] + prod_cost * x[t] + hold_cost * s[t] for t in range(periods)), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
