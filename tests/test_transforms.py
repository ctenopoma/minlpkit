"""transforms の実ソルバーテスト: linearize_product / pwl_sos2。

すべて PySCIPOpt(SCIP)を実際に回す。モックなし。
"""
from __future__ import annotations

import minlpkit as mk
from pyscipopt import Model


def _root_dual(build_fn, sense_max: bool) -> float:
    """presolve/分離/ヒューリスティクスを止めた素のルート緩和の双対境界。

    SCIP の自動補償を切って、定式化そのものの緩和の強さを比べる(FINDINGS.md の方法論)。
    最大化: 双対境界=上界(小さいほど締まっている)。
    """
    m = build_fn()
    m.hideOutput()
    m.setParam("presolving/maxrounds", 0)
    m.setParam("separating/maxroundsroot", 0)
    # 伝播も止めて、定式化そのものが与える生の緩和(双線形は McCormick)を露出させる
    m.setParam("propagating/maxrounds", 0)
    m.setParam("propagating/maxroundsroot", 0)
    m.setParam("limits/nodes", 1)
    m.optimize()
    return m.getDualbound()


# ---- linearize_product ----
#
# maximize y*x  s.t. x + y <= 2, y∈{0,1,2}(整数), x∈[0,2]。
# 真の最適: y=1, x=1 で 1。双線形は McCormick で 2 まで緩む(x=y=1 で w<=2)。
# 厳密線形化(整数分解)は緩和が締まり、ルート上界が 2 未満になる。

def _build_nonlinear() -> Model:
    m = Model("prod_nl")
    y = m.addVar(vtype="I", lb=0, ub=2, name="y")
    x = m.addVar(lb=0, ub=2, name="x")
    m.addCons(x + y <= 2)
    # SCIP は非線形目的を持てないので補助変数 p<=x*y を最大化(McCormick 緩和が効く)
    p = m.addVar(lb=0, name="p")
    m.addCons(p <= x * y)               # 双線形制約
    m.setObjective(p, "maximize")
    return m


def _build_linearized() -> Model:
    m = Model("prod_lin")
    y = m.addVar(vtype="I", lb=0, ub=2, name="y")
    x = m.addVar(lb=0, ub=2, name="x")
    m.addCons(x + y <= 2)
    w = mk.linearize_product(m, y, x, 0, 2, 0.0, 2.0, "w")  # w = y*x を厳密表現
    m.setObjective(w, "maximize")
    return m


def _optimum(build_fn) -> float:
    m = build_fn()
    m.hideOutput()
    m.optimize()
    return m.getObjVal()


def test_linearize_product_exact_optimum():
    """厳密線形化した積の最適値が、双線形定式化の最適値と一致する(等価変換)。"""
    nl = _optimum(_build_nonlinear)
    lin = _optimum(_build_linearized)
    assert abs(nl - 1.0) < 1e-4       # 真の最適 = 1
    assert abs(lin - nl) < 1e-4       # 厳密線形化で最適値不変


def test_linearize_product_tightens_relaxation():
    """厳密線形化がルート緩和を締める(McCormick より上界が小さい)。"""
    nl_root = _root_dual(_build_nonlinear, sense_max=True)
    lin_root = _root_dual(_build_linearized, sense_max=True)
    # 双線形は真の最適 1 を大きく上回る(McCormick で ~2 まで緩む)
    assert nl_root > 1.0 + 1e-3
    # 厳密線形化は締まっており、双線形より小さい上界
    assert lin_root < nl_root - 1e-4


# ---- pwl_sos2 ----
#
# 折れ点 (0,0),(1,-1),(2,0),(3,3) の区分線形関数 f。最小は x=1 で -1。

BRKS = [0.0, 1.0, 2.0, 3.0]
VALS = [0.0, -1.0, 0.0, 3.0]


def test_pwl_sos2_minimum():
    """SOS2 区分線形近似の最小値が既知の折れ点値 -1(x=1)に一致する。"""
    m = Model("pwl_min")
    x = m.addVar(lb=0, ub=3, name="x")
    y = mk.pwl_sos2(m, x, BRKS, VALS, "f")
    m.setObjective(y, "minimize")
    m.hideOutput()
    m.optimize()
    assert abs(m.getObjVal() - (-1.0)) < 1e-4
    assert abs(m.getVal(x) - 1.0) < 1e-4


def test_pwl_sos2_interpolation():
    """区間内の点 x=0.5 で線形補間 f=-0.5 を返す(隣接2点の凸結合)。"""
    m = Model("pwl_interp")
    x = m.addVar(lb=0, ub=3, name="x")
    y = mk.pwl_sos2(m, x, BRKS, VALS, "f")
    m.addCons(x == 0.5)
    m.setObjective(y, "minimize")
    m.hideOutput()
    m.optimize()
    assert abs(m.getVal(y) - (-0.5)) < 1e-4
