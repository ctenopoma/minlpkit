"""plantモデルの非線形項を区間演算で評価する (Phase 2.c)

scheduling_plant.py の実定数・実境界を使い、各非線形項の値域を区間演算で見積もる。
値域(特に相対幅)が大きい項ほど凸緩和が緩く、双対境界の律速になりやすい。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "samples"))

import scheduling_plant as sp  # 実モデルの定数・境界を参照
from viz.interval import Interval


def evaluate_terms() -> pd.DataFrame:
    """plantの各非線形項の値域を区間演算で計算して返す。"""
    T = Interval(sp.T_MIN, sp.T_MAX)          # 反応温度
    tau = Interval(sp.TAU_MIN, sp.TAU_MAX)    # 反応時間
    n = Interval(1, sp.N_MAX)                 # バッチ数
    s = Interval(sp.S_MIN, sp.S_MAX)          # バッチサイズ
    T0 = sp.T0

    # k = A·exp(−Ea/T)
    k = sp.ARRH_A * (Interval(-sp.EA_R, -sp.EA_R) / T).exp()
    # X = 1 − exp(−k·tau)
    X = 1 - (-(k * tau)).exp()
    dT = T - T0

    rows = []

    def add(name, expr, kind, note):
        rows.append(dict(term=name, kind=kind, lo=expr.lo, hi=expr.hi,
                         width=expr.width, rel_width=expr.rel_width, note=note))

    add("k = A·exp(−Ea/T)", k, "arrhenius", "反応速度定数(exp(1/T))")
    add("X = 1−exp(−k·τ)", X, "conversion", "転化率(ネストexp)")
    add("n·s·X (需要)", n * s * X, "demand", "整数×連続×連続の三重積")
    add("n·s·(T−T0) (エネルギー)", n * s * dT, "energy", "三重積・目的に効く")
    add("s·(T−T0)/P (昇温)", s * dT / sp.P_HEAT, "batchtime", "双線形")
    add("ΔH·s·X (発熱, ΔH=平均)", 7.5 * s * X, "cooling", "双線形×X")
    add("k·τ (反応進行度)", k * tau, "conversion", "双線形(expの中身)")
    return pd.DataFrame(rows).sort_values("rel_width", ascending=False).reset_index(drop=True)
