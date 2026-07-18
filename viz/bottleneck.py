"""線形制約のスラック(拘束)とIISの分析 (Phase 2.b)

2つの診断を提供する:
1. スラック/拘束制約: LP緩和解で各線形制約のスラックと双対値(影の価格)を測る。
   スラック≈0 かつ 双対値が大きい制約 = 双対境界を押し下げる強固なボトルネック。
2. IIS(既約不整合部分系): 実行不能モデルに対し、削除フィルタ法で
   「これ以上どれを外しても不能でなくなる」最小の矛盾制約集合を抽出する。
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
from pyscipopt import Model

_INF = 1e19


def analyze_slack(model: Model) -> pd.DataFrame:
    """LP緩和を解き、線形制約ごとのスラック・活動値・双対値を返す。

    双対値は getDualsolLinear(LP緩和の影の価格)。整数変数は連続緩和して解く。
    """
    # 整数性を緩和(LPの双対値を得るため)
    for v in model.getVars():
        if v.vtype() in ("BINARY", "INTEGER"):
            model.chgVarType(v, "CONTINUOUS")
    model.setPresolve(0)          # 制約を潰さず双対値を制約単位で取れるように
    model.setParam("lp/initalgorithm", "s")
    model.hideOutput()
    model.optimize()

    rows = []
    sol = model.getBestSol()
    for c in model.getConss():
        if not c.isLinear():
            continue
        try:
            slack = model.getSlack(c, sol)
            activity = model.getActivity(c, sol)
            dual = model.getDualsolLinear(c)
        except Exception:
            continue
        rows.append(dict(
            constraint=c.name,
            ctype=c.name.rpartition("_")[0] or c.name,
            activity=activity,
            slack=slack,
            abs_slack=abs(slack),
            dual=dual,
            binding=abs(slack) < 1e-6,
        ))
    return pd.DataFrame(rows)


def compute_iis(build_fn: Callable[[set[str]], Model], all_cons: list[str],
                verbose: bool = False) -> tuple[list[str], list[dict]]:
    """削除フィルタ法でIISを求める。

    build_fn(active) は active に含む名前の制約だけを張ったモデルを返す。
    前提: build_fn(all) は実行不能。
    返り値: (IIS制約名リスト, 各試行のログ)
    """
    def infeasible(active: set[str]) -> bool:
        m = build_fn(active)
        m.setParam("limits/solutions", 1)  # 実行可能解が1つ出れば十分
        m.hideOutput()
        m.optimize()
        return m.getStatus() == "infeasible"

    active = set(all_cons)
    assert infeasible(active), "初期モデルが実行不能ではない(IIS抽出の前提を満たさない)"

    log = []
    for c in list(all_cons):
        trial = active - {c}
        still_infeasible = infeasible(trial)
        if still_infeasible:
            active = trial  # c は無くても不能 → IISに不要、恒久的に除去
            log.append(dict(constraint=c, removed=True, note="外しても不能→IISに不要"))
        else:
            log.append(dict(constraint=c, removed=False, note="外すと実行可能→IISに必須"))
        if verbose:
            print(log[-1])
    return sorted(active), log
