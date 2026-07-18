"""列生成(Gilmore-Gomory)とコンパクト定式化のLP緩和比較 (Phase 4)

列生成: 制限付き主問題(restricted master, 連続LP)を解いて双対を得て、
価格付けナップサック(pricing)で被約コストが負のパターンを追加する。
反復を繰り返すとGGのLP緩和境界(材料下界に一致)が得られる。
SCIPが自動でやらない=モデラーが与える真の価値がある再定式化。
"""

from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum
from scipy.optimize import linprog


def solve_master_lp(patterns: list[list[int]], demands: list[int]) -> tuple[float, list[float]]:
    """制限付き主問題(連続LP): min Σλ_p s.t. Σ_p a_ip λ_p >= d_i。目的値と双対を返す。

    双対を確実に得るため scipy.linprog(highs)を使う(PySCIPOptの双対取得はpresolveで
    制約がNULL化する問題があるため)。>= を -Σaλ <= -d に変換して解く。
    """
    P, N = len(patterns), len(demands)
    c = np.ones(P)
    A_ub = np.array([[-patterns[p][i] for p in range(P)] for i in range(N)], dtype=float)
    b_ub = np.array([-demands[i] for i in range(N)], dtype=float)
    res = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=(0, None), method="highs")
    # <= 制約のmarginalは <=0。元の >= 制約の双対 π_i = -marginal >= 0
    duals = (-res.ineqlin.marginals).tolist()
    return float(res.fun), duals


def pricing(duals: list[float], widths: list[int], W: int) -> tuple[list[int], float]:
    """価格付けナップサック: max Σπ_i a_i s.t. Σ w_i a_i <= W, a_i>=0 整数。

    最適値 > 1 なら被約コスト 1 − 値 < 0 の改善パターンが存在。パターンと値を返す。
    """
    m = Model("pricing")
    a = {i: m.addVar(vtype="I", lb=0, ub=W // widths[i], name=f"a_{i}") for i in range(len(widths))}
    m.addCons(quicksum(widths[i] * a[i] for i in range(len(widths))) <= W, name="knap")
    m.setObjective(quicksum(duals[i] * a[i] for i in range(len(widths))), "maximize")
    m.hideOutput()
    m.optimize()
    pattern = [int(round(m.getVal(a[i]))) for i in range(len(widths))]
    return pattern, m.getObjVal()


def column_generation(widths: list[int], demands: list[int], W: int,
                      max_iter: int = 500, alpha: float = 0.0) -> dict:
    """列生成を回してGGのLP緩和境界を求める。反復履歴も返す。

    alpha>0 で双対安定化(smoothing): pricing に使う双対を
        π̃_t = α·π̃_{t-1} + (1−α)·π_t
    と平滑化して双対の振動(tailing-off)を抑える。平滑双対で改善列が出ないときは
    真の双対 π_t で再価格付けし(誤価格付けチェック)、真の最適性への収束を保証する。
    """
    n = len(widths)
    # 初期パターン: 各品目を単独で詰め込む(実行可能な初期基底)
    patterns = [[W // widths[i] if k == i else 0 for i in range(n)] for k in range(n)]
    history = []
    lp = None
    best_L = -1e18       # 最良Lagrange下界(Farley)
    pi_center = None     # Wentges安定化中心(最良Lを与えた双対)
    for it in range(max_iter):
        lp, duals = solve_master_lp(patterns, demands)  # 真の双対 π_t
        # 真の双対での価格付け(収束判定 + Farley下界に使う)
        pat_true, val_true = pricing(duals, widths, W)
        # Farley下界 L = master_obj / pricing_val(pricing>1のとき有効)
        L = lp / val_true if val_true > 1e-9 else lp
        if L > best_L:
            best_L, pi_center = L, duals

        if val_true <= 1 + 1e-6:  # 真の双対で改善列なし → 収束
            history.append(dict(iter=it, lp_bound=lp, dual_bound=best_L,
                                pricing_val=val_true, n_patterns=len(patterns), mispriced=False))
            break

        # 追加する列: 安定化中心へ平滑化した双対で価格付け(Wentges)
        mispriced = False
        if alpha > 0 and pi_center is not None:
            pi_tilde = [alpha * pi_center[i] + (1 - alpha) * duals[i] for i in range(n)]
            pat, val_t = pricing(pi_tilde, widths, W)
            if val_t <= 1 + 1e-6:      # 平滑双対では改善列なし → 真の列にフォールバック
                pat, mispriced = pat_true, True
        else:
            pat = pat_true

        history.append(dict(iter=it, lp_bound=lp, dual_bound=best_L,
                            pricing_val=val_true, n_patterns=len(patterns), mispriced=mispriced))
        patterns.append(pat)
    return dict(lp_bound=lp, dual_bound=best_L, patterns=patterns,
                history=history, n_patterns=len(patterns))


def compact_lp_bound(model: Model) -> float:
    """コンパクト定式化のLP緩和境界(整数性を緩和して解く)。"""
    for v in model.getVars():
        if v.vtype() in ("BINARY", "INTEGER"):
            model.chgVarType(v, "CONTINUOUS")
    model.hideOutput()
    model.setParam("limits/nodes", 1)
    model.optimize()
    return model.getDualbound()
