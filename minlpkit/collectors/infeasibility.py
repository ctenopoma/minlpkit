"""実行不可能(infeasible)モデルの犯人制約特定 (Phase 2.d)

人が infeasible を追うとき「怪しい制約をOff/緩めて原因を絞る」のを自動化する。
2つの相補的な手法を提供する。

- **弾性緩和 (elastic filtering)**: 全線形制約に非負スラック s を足し、Σs を最小化する。
  元が実行不可能でもこの緩和モデルは必ず解け、s>0 になった制約 = 実際に緩めないと
  実行可能にならない箇所。人の「緩めてみる」を全制約同時に定量化したもの。線形制約が対象。
- **削除フィルタ (deletion filter)**: 制約を1本ずつ外して解き直す。外しても依然 infeasible
  ならその制約は犯人ではない→捨てる。最後まで残った集合が極小非可行部分系(IIS,
  Irreducible Infeasible Subsystem)= これ以上減らせない矛盾の核。任意の制約型に効く。

solve前の当たりとして、SCIPのpresolveが自明な矛盾(空定義域・境界矛盾・単純な線形矛盾)を
証明できるかも見る(``presolve_infeasible``)。厳密な核はsolveが要る。

注: ``build_fn`` の戻り値は必ずローカル変数に保持すること。反復中にGCされると
PySCIPOpt がアクセス違反(segfault)や制約名の空文字化を起こす(FINDINGS.md §5)。
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
from pyscipopt import Model, quicksum

_INF = 1e19
BuildFn = Callable[[], Model]


def _ctype(name: str) -> str:
    """制約名からタイプ(末尾の連番/エンティティを落とした接頭辞)を推定する。"""
    ctype, _, _ = name.rpartition("_")
    return ctype or name


def base_status(build_fn: BuildFn, time_limit: float = 10.0) -> str:
    """モデルをそのまま解いて SCIP のステータス文字列を返す(``infeasible`` 等)。"""
    m = build_fn()
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    st = str(m.getStatus())
    del m
    return st


def presolve_infeasible(build_fn: BuildFn) -> bool:
    """presolveだけで実行不可能を証明できるか(solve前の安価な当たり)。

    presolve が矛盾を捕まえれば ``True``。捕まえられなくても(``False``)実行可能とは
    限らない(本探索が要る)ことに注意。
    """
    m = build_fn()
    m.hideOutput()
    try:
        m.presolve()
        st = str(m.getStatus())
    except Exception:
        st = "unknown"
    del m
    return st == "infeasible"


def elastic_filter(build_fn: BuildFn, time_limit: float = 20.0) -> pd.DataFrame:
    """弾性緩和で線形制約ごとの必要違反量(スラック)を返す。

    各線形制約に非負スラックを足して Σ(スラック) を最小化する。返る DataFrame の
    ``slack`` が正の制約 = 実行可能にするために実際に緩める必要がある箇所(=犯人候補)。

    Returns:
        columns=[constraint, ctype, sense, slack]。slack 降順。``status`` 列で
        緩和モデルのステータス(通常 ``optimal``。非線形制約が原因だと解けないことがある)。
        非線形制約はスラックを足せないため対象外(``sense="nonlinear"``, slack=NaN)。
    """
    m = build_fn()
    m.hideOutput()
    m.setParam("limits/time", time_limit)

    slacks: dict[str, list] = {}
    senses: dict[str, str] = {}
    skipped: list[str] = []
    for c in m.getConss():
        name = c.name
        if not c.isLinear():
            skipped.append(name)
            continue
        lhs, rhs = m.getLhs(c), m.getRhs(c)
        two_sided = (lhs > -_INF) and (rhs < _INF) and (lhs != rhs)
        if rhs < _INF:  # g(x) <= rhs を g(x) - s <= rhs に緩める(上側違反)
            s = m.addVar(name=f"__elastic_hi_{name}", lb=0.0)
            m.addConsCoeff(c, s, -1.0)
            slacks.setdefault(name, []).append(s)
        if lhs > -_INF:  # g(x) >= lhs を g(x) + s >= lhs に緩める(下側違反)
            s = m.addVar(name=f"__elastic_lo_{name}", lb=0.0)
            m.addConsCoeff(c, s, 1.0)
            slacks.setdefault(name, []).append(s)
        senses[name] = "range" if two_sided else ("eq" if lhs == rhs else
                                                   ("<=" if rhs < _INF else ">="))

    all_slacks = [s for lst in slacks.values() for s in lst]
    if all_slacks:
        m.setObjective(quicksum(all_slacks), "minimize")
    m.optimize()
    status = str(m.getStatus())

    rows = []
    if status in ("optimal", "gaplimit", "timelimit") and m.getNSols() > 0:
        for name, lst in slacks.items():
            val = sum(max(0.0, m.getVal(s)) for s in lst)
            rows.append(dict(constraint=name, ctype=_ctype(name),
                             sense=senses.get(name, "?"), slack=val))
    for name in skipped:
        rows.append(dict(constraint=name, ctype=_ctype(name),
                         sense="nonlinear", slack=float("nan")))
    del m
    df = pd.DataFrame(rows)
    if not df.empty:
        df["status"] = status
        df = df.sort_values("slack", ascending=False, na_position="last").reset_index(drop=True)
    return df


def deletion_filter(build_fn: BuildFn, time_limit: float = 10.0,
                    max_conss: int = 200) -> dict:
    """削除フィルタで極小非可行部分系(IIS)の制約核を求める。

    制約を1本ずつ外して解き直し、外しても infeasible のままなら犯人ではない→捨てる。
    残った集合が IIS 核。制約 n 本につき最大 n 回 solve するため ``max_conss`` で上限を切る。

    Returns:
        dict: ``core``(核の制約名list)/ ``base_status`` / ``n_conss`` /
        ``truncated``(制約数が上限超で打ち切ったか)/ ``note``。
        元が実行可能なら ``core=[]`` で ``note`` に理由を入れる。
    """
    bstat = base_status(build_fn, time_limit=time_limit)
    m0 = build_fn()
    names = [c.name for c in m0.getConss()]
    del m0

    if bstat != "infeasible":
        return dict(core=[], base_status=bstat, n_conss=len(names), truncated=False,
                    note=f"元モデルは実行不可能ではない(status={bstat})。削除フィルタは適用しない")
    if len(names) > max_conss:
        return dict(core=[], base_status=bstat, n_conss=len(names), truncated=True,
                    note=f"制約{len(names)}本が上限{max_conss}超。弾性緩和スラックで犯人を絞ってから核を取る")

    def _status(drop: set[str]) -> str:
        mm = build_fn()
        mm.hideOutput()
        mm.setParam("limits/time", time_limit)
        for c in list(mm.getConss()):
            if c.name in drop:
                mm.delCons(c)
        mm.optimize()
        st = str(mm.getStatus())
        del mm
        return st

    removed: set[str] = set()
    for n in names:
        # n を追加で外しても infeasible を「証明できた」ときだけ落とす。
        # timelimit 等で証明できない場合は保守的に核へ残す(偽の核を作らない)。
        if _status(removed | {n}) == "infeasible":
            removed.add(n)
    core = [n for n in names if n not in removed]
    return dict(core=core, base_status=bstat, n_conss=len(names), truncated=False,
                note=f"全{len(names)}本 → 核{len(core)}本に縮約")


def diagnose_infeasibility(build_fn: BuildFn, time_limit: float = 10.0,
                           deletion: bool = True, max_deletion_conss: int = 120) -> dict:
    """実行不可能診断を一気通貫で行う(presolve当たり→弾性緩和→削除フィルタ核)。

    Args:
        build_fn: 引数なしで新しい ``Model`` を返す callable。
        time_limit: 各 solve の時間制限[秒]。
        deletion: 削除フィルタ(IIS核)を実行するか。制約が多い/重いモデルでは False に。
        max_deletion_conss: 削除フィルタを実行する制約数の上限。

    Returns:
        dict: ``infeasible`` / ``status`` / ``presolve_infeasible`` / ``elastic``
        (DataFrame) / ``iis_core``(list) / ``n_conss`` / ``metrics``(診断ルール用の
        フラット dict: ``infeasible`` / ``iis_size`` / ``top_elastic_constraint`` /
        ``top_elastic_slack`` / ``n_conss``)。
    """
    status = base_status(build_fn, time_limit=time_limit)
    infeasible = (status == "infeasible")
    pre = presolve_infeasible(build_fn)

    elastic = elastic_filter(build_fn, time_limit=time_limit)
    pos = elastic[elastic["slack"] > 1e-7] if not elastic.empty else elastic
    top_name = str(pos.iloc[0]["constraint"]) if not pos.empty else None
    top_slack = float(pos.iloc[0]["slack"]) if not pos.empty else 0.0

    core: list[str] = []
    core_note = ""
    n_conss = 0
    if deletion:
        dres = deletion_filter(build_fn, time_limit=time_limit, max_conss=max_deletion_conss)
        core, core_note, n_conss = dres["core"], dres["note"], dres["n_conss"]
    else:
        m0 = build_fn()
        n_conss = m0.getNConss()
        del m0

    metrics = dict(infeasible=infeasible, iis_size=len(core), n_conss=n_conss,
                   top_elastic_constraint=top_name, top_elastic_slack=top_slack,
                   presolve_infeasible=pre)
    return dict(infeasible=infeasible, status=status, presolve_infeasible=pre,
                elastic=elastic, iis_core=core, iis_note=core_note,
                n_conss=n_conss, metrics=metrics)
