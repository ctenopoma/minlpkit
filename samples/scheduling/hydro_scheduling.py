"""揚水式水力発電の運転計画 (Pumped-Storage Hydroelectric Scheduling)

事業ストーリー
--------------
電力トレーディング担当者が、揚水式水力発電所の1日(24時間)の運転計画を決める。
電力市場価格は深夜・早朝は安く、夕方の需要ピーク時には高騰する。この価格差を
利用し、価格が安い時間帯には電力を買って水を汲み上げ(揚水)、価格が高い時間帯に
その水を放流して発電・売電することで利益を最大化する。ただし、揚水と発電を
同時には行えず、貯水池の水位には上限・下限があるため、価格予測だけでなく
水位のやりくりも同時に決める必要がある。

各制約の業務的意味:
- **揚水/発電の排他制約**: 1つのポンプ・発電設備を同時に「汲み上げ」と「放流」の
  両方には使えない(物理的に排他)。
- **貯水池の水位ダイナミクス**: ある時刻の水位は、直前の水位に揚水量(効率を掛けた
  増加分)を足し、発電量(効率で割った減少分)を引いたものになる。
  ポンプ・発電のエネルギー変換効率(90%)による目減りを考慮する。
- **貯水池容量の上限・下限**: 水位が満水を超えたり空になったりしないよう、
  各時間帯の水位を容量範囲内に収める。
- **利益最大化**: 発電による売電収入から揚水にかかる買電コストを差し引いた
  利益を最大化する(PySCIPOptは最小化のみのため、符号を反転して最小化する)。

(元の参考文献: Garcia-Gonzalez, J., de la Muela, R. M. R., Santos, L. M., & Gonzalez, A. M. (2007).
Stochastic joint optimization of wind generation and pumped-storage units in an electricity market.
IEEE Transactions on power systems, 23(2), 460-468.)
"""

from pyscipopt import Model

def build_model(infeasible=False):
    m = Model("Hydro_Scheduling")

    # 24時間分の時間帯別電力価格(深夜・早朝は安く、夕方ピークで高騰する典型的な日内カーブ)
    T = 24
    prices = [18, 16, 15, 14, 14, 15, 20, 28, 35, 32, 28, 25,
              22, 20, 22, 26, 32, 45, 55, 48, 38, 30, 24, 20]
    p_max = 60
    g_max = 60
    v_max = 500
    v_init = 250
    eff = 0.9

    if infeasible:
        v_max = -10

    # Variables
    pump = {}
    gen = {}
    vol = {}
    is_pump = {}

    for t in range(T):
        pump[t] = m.addVar(vtype="C", lb=0, ub=p_max, name=f"pump_{t}")
        gen[t] = m.addVar(vtype="C", lb=0, ub=g_max, name=f"gen_{t}")
        vol[t] = m.addVar(vtype="C", lb=0, ub=v_max, name=f"vol_{t}")
        is_pump[t] = m.addVar(vtype="B", name=f"is_pump_{t}")

    # Objective (Maximize profit)
    # PySCIPOpt minimizes by default, so we minimize -profit
    profit = sum(prices[t] * (gen[t] - pump[t]) for t in range(T))
    m.setObjective(-profit, "minimize")

    # Constraints
    for t in range(T):
        # Mutual exclusion
        m.addCons(pump[t] <= p_max * is_pump[t], name=f"Pump_Exc_{t}")
        m.addCons(gen[t] <= g_max * (1 - is_pump[t]), name=f"Gen_Exc_{t}")

        # Volume dynamics
        if t == 0:
            m.addCons(vol[t] == v_init + eff * pump[t] - gen[t] / eff, name=f"Vol_Dyn_{t}")
        else:
            m.addCons(vol[t] == vol[t-1] + eff * pump[t] - gen[t] / eff, name=f"Vol_Dyn_{t}")

    return m

def main():
    m = build_model()
    m.optimize()
    if m.getStatus() == "optimal":
        print("Optimal value:", -m.getObjVal())
    else:
        print("Status:", m.getStatus())

if __name__ == "__main__":
    main()
