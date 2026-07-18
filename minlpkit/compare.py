"""改善のbefore/after比較harness (Phase 5, 汎用化)。

run_improve_* で個別にやっていた「定式化/設定の変種を測って並べる」を汎用化する。
交絡を避けるため、指標はルート双対境界・時間制限gap・ノード数を分けて取る。
"""

from __future__ import annotations

from typing import Callable

import pandas as pd

_INF = 1e19


def _clean(v: float):
    return None if abs(v) >= _INF else v


def measure(build_fn: Callable[[], "object"], time_limit: float = 20.0,
            root_only: bool = False) -> dict:
    """1つの定式化/設定を測る。

    Args:
        build_fn: 引数なしで ``Model`` を返す callable。
        time_limit: ``root_only=False`` のときの時間制限[秒]。
        root_only: True でルート1ノードのみ求解しルート双対境界を測る(探索動学に
            交絡されない定式化の質の指標)。False で time_limit まで通常求解する。

    Returns:
        dict: ``dual`` / ``primal`` / ``gap`` / ``nodes`` / ``time`` / ``status``。
        無限大は None に正規化される。
    """
    m = build_fn()
    m.hideOutput()
    m.setParam("timing/clocktype", 2)
    if root_only:
        m.setParam("limits/nodes", 1)
    else:
        m.setParam("limits/time", time_limit)
        m.setParam("limits/gap", 0.01)
    m.optimize()
    return dict(
        dual=_clean(m.getDualbound()),
        primal=_clean(m.getPrimalbound()) if m.getNSols() > 0 else None,
        gap=m.getGap() if m.getGap() < _INF else None,
        nodes=m.getNNodes(),
        time=m.getSolvingTime(),
        status=str(m.getStatus()),
    )


def compare_variants(variants: dict[str, Callable[[], "object"]],
                     time_limit: float = 20.0) -> pd.DataFrame:
    """改善の before/after を測って1つの DataFrame に並べる。

    各変種をルート双対境界(``root_only``)と時間制限求解の両方で測る。定式化の質は
    ルート双対境界で、実際の求解性能は時間制限gap/ノードで比較できる(交絡を分離)。

    Args:
        variants: ``{変種名: build_fn}``。各 build_fn は引数なしで ``Model`` を返す。
        time_limit: 各変種の時間制限求解の制限[秒]。

    Returns:
        pandas.DataFrame: 1変種1行。列は ``variant`` / ``root_dual`` / ``final_dual`` /
        ``final_gap`` / ``nodes`` / ``time`` / ``status``。

    Example:
        >>> import minlpkit as mk
        >>> from pyscipopt import Model
        >>> def loose():
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(vtype="I", lb=0, ub=10); m.addCons(x <= 3)
        ...     m.setObjective(x, "maximize"); return m
        >>> def tight():
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(vtype="I", lb=0, ub=3)
        ...     m.setObjective(x, "maximize"); return m
        >>> df = mk.compare_variants({"loose": loose, "tight": tight}, time_limit=5)
        >>> list(df["variant"])
        ['loose', 'tight']
    """
    rows = []
    for name, build_fn in variants.items():
        root = measure(build_fn, root_only=True)
        full = measure(build_fn, time_limit=time_limit)
        rows.append(dict(
            variant=name,
            root_dual=root["dual"],
            final_dual=full["dual"],
            final_gap=full["gap"],
            nodes=full["nodes"],
            time=full["time"],
            status=full["status"],
        ))
    return pd.DataFrame(rows)
