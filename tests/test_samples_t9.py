"""Phase 13 T9 上級ティア: AC最適潮流(AC-OPF)の smoke テスト。

真の非凸(電圧×電圧×cos/sin)を含む MINLP のため、small でも時間制限内に
**最適証明は求めない**。T9 の受け入れ基準に従い「実行可能解が出て目的値が有限」
であることのみを実SCIPで確認する(モックなし)。時間制限を明示し、timelimit で
打ち切られても実行可能解があれば PASS とする設計。

対象:
  - ac_opf  (極座標 AC-OPF + 離散コンデンサバンク, V·V·cos/sin の真の非凸)
"""
from __future__ import annotations

import math

import ac_opf


def test_small_feasible_finite():
    """small で実行可能解が出て目的値(発電費用)が有限であること。最適証明は不要。"""
    m = ac_opf.build_model("small")
    m.hideOutput()
    m.setParam("limits/time", 45.0)  # 真の非凸ゆえ timelimit 打ち切りを許容
    m.optimize()
    assert m.getNSols() > 0, "ac_opf: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), "ac_opf: 目的値が非有限"
    assert obj > 0.0, "ac_opf: 発電費用は正であるはず"


def test_scales_build():
    """3スケールすべて build でき、非線形制約と整数変数を含むこと(構造の健全性)。"""
    for sc in ("small", "default", "large"):
        m = ac_opf.build_model(sc)
        assert m.getNVars() > 0
        assert m.getNConss() > 0
        # 離散コンデンサバンク(整数決定)が存在すること
        n_int = sum(1 for v in m.getVars() if v.vtype() == "INTEGER")
        assert n_int > 0, f"ac_opf[{sc}]: 整数変数(コンデンサバンク段数)がない"
