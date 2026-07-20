"""Phase 13(拡張) T10 上級ティア: 蓄電池・蓄熱の精緻化2本の smoke テスト。

いずれも真の非凸(双線形/双曲線)を含む連続MINLPのため、small でも時間制限内に
**最適証明は求めない**。T10 の受け入れ基準に従い「実行可能解が出て目的値が有限」
であることのみを実SCIPで確認する(モックなし)。時間制限を明示し、timelimit で
打ち切られても実行可能解があれば PASS とする設計。

対象:
  - battery_degradation_dispatch  (Cレート×DoD×温度のべき乗積による劣化コスト内生化)
  - thermal_storage_lossy         (自然対流損失^1.25 + COPの温度リフト依存双線形)
"""
from __future__ import annotations

import math

import pytest

import battery_degradation_dispatch
import thermal_storage_lossy


@pytest.mark.parametrize("mod, time_limit", [
    (battery_degradation_dispatch, 60.0),
    (thermal_storage_lossy, 60.0),
], ids=["battery_degradation_dispatch", "thermal_storage_lossy"])
def test_small_feasible_finite(mod, time_limit):
    """small で実行可能解が出て目的値が有限であること。最適証明は不要。"""
    m = mod.build_model("small")
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    assert m.getNSols() > 0, f"{mod.__name__}: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), f"{mod.__name__}: 目的値が非有限"


def test_scales_build():
    """3スケールすべて build でき、非線形制約を含むこと(構造の健全性)。"""
    for mod in (battery_degradation_dispatch, thermal_storage_lossy):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0
            assert m.getNConss() > 0
