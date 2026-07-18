"""モデリング変換ヘルパー (Phase 7, 任意モデルに適用可能)

サンプル埋め込みだった改善を、任意の項に適用できる再利用可能な関数にしたもの。
モデラーは「この項をこう直す」と1行呼ぶだけで再定式化できる(=横展開)。
"""

from __future__ import annotations

from pyscipopt import Constraint, Model, Variable, quicksum


def linearize_product(model: Model, y_int: Variable, x_cont: Variable,
                      y_lb: int, y_ub: int,
                      x_lb: float, x_ub: float, name: str) -> Variable:
    """整数 y∈[y_lb,y_ub] と連続 x∈[x_lb,x_ub] の積 y·x を厳密線形化する。

    y は整数なので、指示変数 δ_v(y=v)と x の分解 x=Σ_v x_v(x_v は y=v のとき有効)で
    w = Σ_v v·x_v が y·x を厳密に表す(McCormick緩和のギャップ0)。SCIP が双線形項に
    使う McCormick 緩和よりも下界が締まるため、非凸緩和の弱さが律速のモデルで効く。

    Args:
        model: 変数・制約を追加する対象の PySCIPOpt ``Model``。
        y_int: 整数変数(積の一方)。
        x_cont: 連続変数(積の他方)。
        y_lb: y の下限(整数)。
        y_ub: y の上限(整数)。分解サイズは ``y_ub - y_lb + 1`` に比例する。
        x_lb: x の下限。
        x_ub: x の上限。
        name: 追加する変数・制約名の接頭辞。

    Returns:
        Var: 積 y·x を厳密に表す新しい連続変数 w(``[y_lb·x_lb, y_ub·x_ub]``)。

    Note:
        y の値域 ``[y_lb, y_ub]`` が広いと補助変数・制約が線形に増える。整数側の値域が
        小さい積(例: バッチ数×バッチサイズ)に向く。

    Example:
        >>> from pyscipopt import Model
        >>> import minlpkit as mk
        >>> m = Model()
        >>> n = m.addVar(vtype="I", lb=1, ub=3, name="n")
        >>> s = m.addVar(lb=0.0, ub=10.0, name="s")
        >>> ns = mk.linearize_product(m, n, s, 1, 3, 0.0, 10.0, "ns")
        >>> _ = m.addCons(ns >= 12)          # n·s >= 12 が厳密線形制約になる
        >>> m.setObjective(n + s, "minimize")
        >>> m.hideOutput(); m.optimize()
        >>> round(m.getVal(ns), 2)
        12.0
    """
    vals = range(int(y_lb), int(y_ub) + 1)
    delta = {v: model.addVar(vtype="B", name=f"{name}_d{v}") for v in vals}
    xv = {v: model.addVar(lb=0, name=f"{name}_x{v}") for v in vals}
    w = model.addVar(lb=y_lb * x_lb, ub=y_ub * x_ub, name=name)

    model.addCons(quicksum(delta[v] for v in vals) == 1, name=f"{name}_sel")
    model.addCons(y_int == quicksum(v * delta[v] for v in vals), name=f"{name}_y")
    model.addCons(x_cont == quicksum(xv[v] for v in vals), name=f"{name}_x")
    for v in vals:
        model.addCons(xv[v] <= x_ub * delta[v], name=f"{name}_ub{v}")
        model.addCons(xv[v] >= x_lb * delta[v], name=f"{name}_lb{v}")
    model.addCons(w == quicksum(v * xv[v] for v in vals), name=f"{name}_w")
    return w


def perspective_quadratic(model: Model, u_bin: Variable, p_cont: Variable,
                          fc_var: Variable,
                          a: float, b: float, c: float, name: str) -> Constraint:
    """半連続な二次費用の perspective(遠近)再定式化を適用する。

    on/off バイナリ u と半連続な出力 p(u=0 なら p=0)に対し、二次費用の下界
    ``fc >= a·u + b·p + c·p^2`` を、二次項だけ perspective 化した
    ``fc >= a·u + b·p + c·p^2/u`` に締める。u で払って
    ``c·p^2 <= (fc − a·u − b·p)·u`` の一般非線形制約として model に追加する。
    ベースライン(素の凸二次下界)を置き換える形で1本呼ぶだけで適用できる。

    Args:
        model: 制約を追加する対象の ``Model``。
        u_bin: on/off バイナリ変数。
        p_cont: 半連続な出力変数(u=0 のとき 0)。
        fc_var: 費用を表す変数(この下界で締める対象)。
        a: 線形係数(u に対する固定費相当)。
        b: 線形係数(p に対する係数)。
        c: 二次係数(``c·p^2`` の係数)。
        name: 追加する制約名。

    Returns:
        Constraint: 追加した perspective 制約オブジェクト。

    Warning:
        FINDINGS.md 参照。この形は理論上は凸包を締めるが、SCIP は右辺の双線形
        (fc·u, u^2, p·u)を McCormick で緩和するため、素の分枝限定ではむしろ緩和が
        弱くなる(UC 実測 −49%)。既定 SCIP では presolve/分離が baseline を自動で
        締めるためルート双対境界はほぼ不変。等価変換なので最適値は不変だが、SCIP に
        対しては素の凸二次下界の方が有利。横展開部品として提供するが常用は推奨しない。

    Example:
        >>> from pyscipopt import Model
        >>> import minlpkit as mk
        >>> m = Model()
        >>> u = m.addVar(vtype="B", name="u")
        >>> p = m.addVar(lb=0.0, ub=5.0, name="p")
        >>> fc = m.addVar(lb=0.0, name="fc")
        >>> _ = mk.perspective_quadratic(m, u, p, fc, a=1.0, b=2.0, c=0.5, name="persp")
    """
    return model.addCons(
        c * p_cont * p_cont <= (fc_var - a * u_bin - b * p_cont) * u_bin,
        name=name,
    )


def pwl_sos2(model: Model, x: Variable, breakpoints: list[float],
             values: list[float], name: str) -> Variable:
    """1変数関数 y=f(x) の区分線形近似を SOS2 で表す(Big-M不要)。

    折れ点 (breakpoints[k], values[k]) の隣接2点の凸結合。重み λ に SOS2(隣接2重みのみ
    非ゼロ)を課すことで、バイナリ変数を使わずに区分線形性を表現する。Big-M や Indicator の
    代わりになる非凸1変数関数の近似手段。

    Args:
        model: 変数・制約を追加する対象の ``Model``。
        x: 独立変数(定義域上の点)。
        breakpoints: 折れ点の x 座標(昇順)。``values`` と同じ長さ。
        values: 各折れ点での関数値 f(breakpoints[k])。
        name: 追加する変数・制約名の接頭辞。

    Returns:
        Var: 近似値 y ≈ f(x) を表す新しい変数。

    Note:
        breakpoints は昇順で与える。区分数を増やすほど近似精度は上がるが λ 変数も増える。

    Example:
        >>> from pyscipopt import Model
        >>> import minlpkit as mk
        >>> m = Model()
        >>> x = m.addVar(lb=0.0, ub=2.0, name="x")
        >>> # f(x)=x^2 を3点で区分線形近似
        >>> y = mk.pwl_sos2(m, x, [0.0, 1.0, 2.0], [0.0, 1.0, 4.0], "sq")
        >>> _ = m.addCons(x == 1.0)
        >>> m.setObjective(y, "minimize"); m.hideOutput(); m.optimize()
        >>> round(m.getVal(y), 2)
        1.0
    """
    K = len(breakpoints)
    lam = [model.addVar(lb=0, ub=1, name=f"{name}_l{k}") for k in range(K)]
    y = model.addVar(lb=min(values) - abs(min(values)) - 1, ub=max(values) + 1, name=name)
    model.addCons(quicksum(lam) == 1, name=f"{name}_cvx")
    model.addCons(x == quicksum(breakpoints[k] * lam[k] for k in range(K)), name=f"{name}_x")
    model.addCons(y == quicksum(values[k] * lam[k] for k in range(K)), name=f"{name}_y")
    model.addConsSOS2(lam, name=f"{name}_sos2")
    return y
