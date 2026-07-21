"""固定費付き生産計画 (MILP) — Big-M改善の実証用

各施設 i は開設(y_i=1)して初めて生産 x_i>0 できる。開設に固定費 f_i。
連動制約 x_i <= M_i·y_i の Big-M の張り方で LP緩和の強さが激変する:
  loose     : M_i = 巨大定数(需要総和など)→ LP緩和が非常に弱い(y_iが極小の分数でOK)
  tight     : M_i = 実際に可能な最大生産量 = min(容量, 総需要)→ LP緩和が締まる
  indicator : SCIPのIndicator制約(y_i=0 ⟹ x_i=0)→ Big-Mを使わず最も締まる

「Big-M排除(Indicator/SOS)」の効果を root LP 境界で明確に示す題材。
"""

from __future__ import annotations

from pyscipopt import Model, quicksum

# 施設 i: (固定費, 単位生産費, 容量)。8施設・需要を容量分布の境目に置き分枝を要する
FACILITIES = {
    "F1": dict(fixed=1000, unit=4, cap=70),
    "F2": dict(fixed=1500, unit=3, cap=90),
    "F3": dict(fixed=800,  unit=5, cap=60),
    "F4": dict(fixed=1200, unit=4, cap=80),
    "F5": dict(fixed=900,  unit=6, cap=65),
    "F6": dict(fixed=1100, unit=5, cap=75),
    "F7": dict(fixed=1300, unit=3, cap=85),
    "F8": dict(fixed=950,  unit=6, cap=55),
}
DEMAND = 380
BIG_M_LOOSE = 100000  # わざと緩い巨大定数


def build_model(bigm: str = "tight") -> Model:
    assert bigm in ("loose", "tight", "indicator")
    m = Model(f"fixed_charge_{bigm}")
    y = {i: m.addVar(vtype="B", name=f"y_{i}") for i in FACILITIES}
    x = {i: m.addVar(lb=0, ub=FACILITIES[i]["cap"], name=f"x_{i}") for i in FACILITIES}

    m.addCons(quicksum(x[i] for i in FACILITIES) >= DEMAND, name="demand")

    for i, fac in FACILITIES.items():
        if bigm == "loose":
            m.addCons(x[i] <= BIG_M_LOOSE * y[i], name=f"link_{i}")
        elif bigm == "tight":
            # 実際に可能な最大生産量 = min(容量, 総需要)
            m.addCons(x[i] <= min(fac["cap"], DEMAND) * y[i], name=f"link_{i}")
        else:  # indicator: y_i=0 ⟹ x_i<=0
            m.addConsIndicator(x[i] <= 0, binvar=y[i], activeone=False, name=f"link_{i}")

    m.setObjective(
        quicksum(FACILITIES[i]["fixed"] * y[i] + FACILITIES[i]["unit"] * x[i]
                 for i in FACILITIES), "minimize")
    m.data = dict(x=x, y=y)
    return m


def lp_relaxation_bound(bigm: str) -> float:
    """純粋なLP緩和境界(presolve/cut/heurを切って初期LP双対境界を見る)。"""
    m = build_model(bigm)
    m.hideOutput()
    m.setParam("presolving/maxrounds", 0)
    m.setParam("separating/maxrounds", 0)
    m.setParam("separating/maxroundsroot", 0)
    m.setParam("limits/nodes", 1)
    m.optimize()
    return m.getDualbound()


def main() -> None:
    print("純粋LP緩和境界(presolve/cut off)— 大きいほど強い緩和:")
    for bigm in ("loose", "tight", "indicator"):
        print(f"  {bigm:10s}: LP緩和境界 = {lp_relaxation_bound(bigm):.1f}")


if __name__ == "__main__":
    main()
