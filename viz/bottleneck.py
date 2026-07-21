"""線形制約のスラック(拘束・影の価格)の分析 (Phase 2.b)

LP緩和解で各線形制約のスラックと双対値(影の価格)を測る。スラック≈0 かつ 双対値が
大きい制約 = 双対境界を押し下げる強固なボトルネック(実行可能なモデルが対象)。

実行不能(infeasible)モデルの矛盾制約特定(IIS核 = 削除フィルタ、必要な緩和量 = 弾性緩和)は
``minlpkit.collectors.infeasibility`` に一本化した(``mk.deletion_filter`` / ``mk.elastic_filter`` /
``mk.diagnose_infeasibility``)。旧 ``compute_iis``(active-set ビルダー契約)はそちらの
delete-by-name 実装へ置き換え済み。
"""

from __future__ import annotations

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
