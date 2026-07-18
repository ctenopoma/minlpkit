"""アルゴリズムフレームワーク (Phase 7.2, コールバック方式の汎用ドライバ)

サンプル埋め込みだったベンダーズ/列生成を、問題固有部分だけを差し替える再利用可能な
ドライバにしたもの。モデラーは pricing_fn / master_build / subproblem_solve を渡すだけ。

- column_generation(rhs, init_columns, pricing_fn): 汎用列生成(Gilmore-Gomory型・Wentges安定化)
- price_and_branch(...): 列生成後に整数制限主問題を解いて整数解を得る(branch-and-price)
- benders(master_build, subproblem_solve): 汎用ベンダーズ(最適性カット)
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from pyscipopt import Model, quicksum
from scipy.optimize import linprog

# ---------- 列生成 ----------

PricingFn = Callable[[list], tuple[list, float]]  # duals -> (column, value)


def _master_lp(columns: list[list[int]], rhs: list[float]) -> tuple[float, list[float]]:
    """min Σλ_p s.t. Σ_p col_p·λ_p >= rhs, λ>=0。目的値と双対を返す(scipy)。"""
    P, N = len(columns), len(rhs)
    c = np.ones(P)
    A_ub = -np.array(columns, dtype=float).T  # (N,P): -col_p[i]
    b_ub = -np.array(rhs, dtype=float)
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
    return float(res.fun), (-res.ineqlin.marginals).tolist()


def column_generation(rhs: list[float], init_columns: list[list[int]],
                      pricing_fn: PricingFn, alpha: float = 0.0,
                      max_iter: int = 500) -> dict:
    """汎用列生成(Gilmore-Gomory 型)。問題固有は pricing_fn だけ。

    制限主問題 ``min Σλ s.t. Σ col·λ >= rhs`` を LP で解き、双対 π を pricing_fn に渡して
    改善列(被約コスト負)を1本ずつ追加する。pricing の返す value>1 が改善列の存在を表す。
    alpha>0 で Wentges 双対安定化(退化問題で反復数を減らす)。

    Args:
        rhs: 主問題の右辺(需要ベクトル)。長さ N。
        init_columns: 初期列の集合。各列は長さ N の整数リスト。
        pricing_fn: ``duals(list[float]) -> (column: list[int], value: float)``。
            与えた双対の下で最良の列とその評価値(>1 なら改善列)を返す問題固有の関数。
        alpha: Wentges 安定化係数 [0,1)。0 で無効。過大(0.9等)は過剰安定化で未収束。
        max_iter: 最大反復数。

    Returns:
        dict: ``lp_bound``(最終LP境界), ``dual_bound``(最良Farley下界),
        ``columns``(生成列を含む全列), ``history``(反復ログのlist[dict]),
        ``n_cols``(最終列数)。

    Note:
        LP境界の強さではなく「指数的な列を列挙せず暗黙に扱う」ことが列生成の価値。
        対応する worked example: ``experiments/run_colgen.py`` → ``results/colgen.html``。

    Example:
        >>> import minlpkit as mk
        >>> # カッティングストック: 幅[3,4,5], 需要[3,3,3], 素材幅10
        >>> widths, rhs, W = [3, 4, 5], [3.0, 3.0, 3.0], 10
        >>> init = [[3, 0, 0], [0, 2, 0], [0, 0, 2]]  # 各幅だけのパターン
        >>> def pricing(duals):
        ...     from pyscipopt import Model
        ...     kp = Model(); kp.hideOutput()
        ...     a = [kp.addVar(vtype="I", lb=0, name=f"a{i}") for i in range(3)]
        ...     kp.addCons(sum(widths[i] * a[i] for i in range(3)) <= W)
        ...     kp.setObjective(sum(duals[i] * a[i] for i in range(3)), "maximize")
        ...     kp.optimize()
        ...     return [round(kp.getVal(v)) for v in a], kp.getObjVal()
        >>> res = mk.column_generation(rhs, init, pricing)
        >>> res["lp_bound"] <= 4.0 + 1e-6   # LP境界は真の整数最適4以下(妥当な下界)
        True
    """
    N = len(rhs)
    columns = [list(c) for c in init_columns]
    history = []
    lp = None
    best_L, pi_center = -1e18, None
    for it in range(max_iter):
        lp, duals = _master_lp(columns, rhs)
        col_true, val_true = pricing_fn(duals)
        L = lp / val_true if val_true > 1e-9 else lp
        if L > best_L:
            best_L, pi_center = L, duals
        if val_true <= 1 + 1e-6:
            history.append(dict(iter=it, lp_bound=lp, dual_bound=best_L,
                                pricing_val=val_true, n_cols=len(columns)))
            break
        if alpha > 0 and pi_center is not None:
            pi_t = [alpha * pi_center[i] + (1 - alpha) * duals[i] for i in range(N)]
            col, val_t = pricing_fn(pi_t)
            if val_t <= 1 + 1e-6:
                col = col_true
        else:
            col = col_true
        history.append(dict(iter=it, lp_bound=lp, dual_bound=best_L,
                            pricing_val=val_true, n_cols=len(columns)))
        columns.append(col)
    return dict(lp_bound=lp, dual_bound=best_L, columns=columns,
                history=history, n_cols=len(columns))


def price_and_branch(rhs: list[float], init_columns: list[list[int]],
                     pricing_fn: PricingFn, alpha: float = 0.0) -> dict:
    """列生成でLP境界と列を得た後、生成列上で整数主問題を解き整数解を得る(branch-and-price)。

    ``column_generation`` を回して列を得たのち、その列だけを使った制限主問題を整数変数で
    解く。返す整数解は真の整数最適の**上界**であり、列が十分でなければ最適とは限らない。

    Args:
        rhs: 主問題の右辺(需要ベクトル)。長さ N。
        init_columns: 初期列。各列は長さ N の整数リスト。
        pricing_fn: ``duals -> (column, value)``。``column_generation`` と同じ。
        alpha: Wentges 安定化係数 [0,1)。

    Returns:
        dict: ``lp_bound``(列生成のLP境界=下界), ``lp_lb``(その天井=整数下界),
        ``int_obj``(生成列上の整数解=上界), ``n_cols``, ``history``。
        ``lp_lb == int_obj`` なら最適性が証明される。

    Warning:
        生成列上の整数解は**上界のみ**を保証する(≥ 真の整数最適)。厳密な整数最適には
        pricing を分枝ノードで呼ぶ完全な branch-and-price が必要。FINDINGS.md §4 参照。

    Note:
        対応する worked example: ``experiments/run_bnp.py`` → ``results/bnp.html``。
    """
    cg = column_generation(rhs, init_columns, pricing_fn, alpha=alpha)
    cols = cg["columns"]
    m = Model("restricted_master_ip")
    lam = [m.addVar(vtype="I", lb=0, name=f"lam_{p}") for p in range(len(cols))]
    for i in range(len(rhs)):
        m.addCons(quicksum(cols[p][i] * lam[p] for p in range(len(cols))) >= rhs[i])
    m.setObjective(quicksum(lam), "minimize")
    m.hideOutput()
    m.optimize()
    import math
    return dict(lp_bound=cg["lp_bound"], lp_lb=math.ceil(cg["lp_bound"] - 1e-6),
                int_obj=m.getObjVal(), n_cols=len(cols), history=cg["history"])


# ---------- ベンダーズ ----------


def benders(master_build: Callable[[list], "Model"],
            subproblem_solve: Callable[[dict], tuple[float, dict]],
            max_iter: int = 50, tol: float = 1e-6) -> dict:
    """汎用ベンダーズ分解(最適性カット)。問題固有は2つのコールバックだけ。

    主問題(連結変数 y と補助変数 eta を持つ)とサブ問題(y を固定した残り)を交互に解く。
    サブの双対から最適性カット ``eta >= Q(ŷ) + Σ grad·(y − ŷ)`` を主問題に足していく。
    下界(主問題目的)と上界(真のサブ費用)が収束するまで反復する。

    Args:
        master_build: ``cuts(list[dict]) -> Model``。与えた cuts を最適性カットとして
            張った主問題を返す。``model.data`` に ``{'eta': etaの変数, 'y': {key: 連結変数}}``
            を入れること。各 cut は ``{'Q': float, 'grad': {key: float}, 'yhat': {key: float}}``
            で、master_build 側で ``eta >= Q + Σ grad[key]*(y[key]-yhat[key])`` を張る。
        subproblem_solve: ``y_hat({key: float}) -> (Q: float, grad: {key: float})``。
            連結変数を固定したサブ問題を解き、費用 Q と劣勾配 grad を返す。
        max_iter: 最大反復数。
        tol: 収束判定の上界−下界のしきい値。

    Returns:
        dict: ``lb``(最終下界), ``ub``(最良上界), ``best_y``(最良の連結変数値),
        ``history``(反復ログ), ``n_cuts``(生成カット数)。

    Note:
        主問題が小さく保たれサブが独立求解可能なブロック構造に効く。実行可能性カットは
        扱わない(サブが常に実行可能になるようモデル化する前提)。
        対応する worked example: ``experiments/run_benders.py`` → ``results/benders.html``。
    """
    cuts, best_ub, best_y, history = [], float("inf"), None, []
    lb = None
    for it in range(max_iter):
        m = master_build(cuts)
        m.hideOutput()
        m.optimize()
        y_hat = {k: m.getVal(v) for k, v in m.data["y"].items()}
        eta_hat = m.getVal(m.data["eta"])
        lb = m.getObjVal()
        Q, grad = subproblem_solve(y_hat)
        ub = lb - eta_hat + Q  # 主問題目的の eta を真のサブ費用 Q に置換
        if ub < best_ub:
            best_ub, best_y = ub, y_hat
        history.append(dict(iter=it, lb=lb, ub=best_ub, gap=best_ub - lb))
        if best_ub - lb <= tol:
            break
        cuts.append(dict(Q=Q, grad=grad, yhat=y_hat))
    return dict(lb=lb, ub=best_ub, best_y=best_y, history=history, n_cuts=len(cuts))
