"""対称性の兆候検出 (Phase 2.c)

変数の構造シグネチャ(1-hop color refinement)で「入れ替えても問題が変わらない」
変数群を検出する。完全な自己同型群ではないが、健全(偽陽性を出しにくい):
シグネチャに「変数自身の係数」と「所属する制約全体の形状(全係数の多重集合・符号・RHS)」を
含めるため、恒等な並列機械のような対称性は捉えつつ、係数/RHSが異なる変数は区別する。

同一シグネチャの変数群(サイズ≥2)= 対称性候補。辞書式順序制約(Phase 3)の対象になる。
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
from pyscipopt import Model

_INF = 1e19


def _constraint_shape(model: Model, c) -> tuple:
    """制約の形状: (下辺, 上辺, 全係数の多重集合)。RHS/符号/係数分布で制約を特徴づける。"""
    vals = model.getValsLinear(c)
    coeffs = tuple(sorted(round(v, 6) for v in vals.values()))
    lhs, rhs = model.getLhs(c), model.getRhs(c)
    # 無限は ±inf(ソート可能な番兵)にする
    lo = float("-inf") if abs(lhs) >= _INF else round(lhs, 6)
    hi = float("inf") if abs(rhs) >= _INF else round(rhs, 6)
    return (lo, hi, coeffs)


def detect_symmetry(model: Model) -> tuple[pd.DataFrame, dict]:
    """線形制約からシグネチャを作り、対称(入替可能)な変数群を返す。

    返り値: (グループのDataFrame[signature_id, size, members], サマリdict)
    """
    var_terms: dict[str, list] = defaultdict(list)
    n_nonlinear = 0
    for c in model.getConss():
        if not c.isLinear():
            n_nonlinear += 1
            continue
        shape = _constraint_shape(model, c)
        for vname, coef in model.getValsLinear(c).items():
            # (変数自身の係数, その制約の形状) を1つの項として蓄積
            var_terms[vname].append((round(coef, 6), shape))

    varobj = {v.name: v for v in model.getVars()}
    sigs: dict[tuple, list[str]] = defaultdict(list)
    for name, terms in var_terms.items():
        v = varobj[name]
        sig = (v.vtype(), round(v.getObj(), 6),
               round(v.getLbGlobal(), 6), round(v.getUbGlobal(), 6),
               tuple(sorted(terms)))
        sigs[sig].append(name)

    groups = [sorted(names) for names in sigs.values() if len(names) >= 2]
    groups.sort(key=len, reverse=True)
    rows = [dict(signature_id=i, size=len(g), members=", ".join(g))
            for i, g in enumerate(groups)]
    df = pd.DataFrame(rows)

    n_sym_vars = sum(len(g) for g in groups)
    # 非線形制約があると線形のみのシグネチャは不完全 → 判定は不確定(偽陽性の恐れ)。
    # 全制約が線形のときだけ健全に対称性を主張できる。
    sound = n_nonlinear == 0
    summary = dict(
        n_linear_vars=len(var_terms),
        n_groups=len(groups),
        n_symmetric_vars=n_sym_vars,
        largest_group=len(groups[0]) if groups else 0,
        n_nonlinear_conss=n_nonlinear,
        sound=sound,
        # 健全なときのみ True/False。非線形ありは None(不確定)
        has_symmetry=(len(groups) > 0) if sound else None,
        caveat=None if sound else
        "非線形制約を含むため線形部分構造のみの判定(定数差で対称性が崩れる可能性=不確定)",
    )
    return df, summary
