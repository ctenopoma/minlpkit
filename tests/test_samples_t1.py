"""Phase 13 T1 プロセス産業クラスタ 3モデルの smoke テスト。

各モデルの ``build_model("small")`` が
  - 実行可能解を出し(nsols > 0)
  - 目的値が有限
であることを実SCIPで軽く確認する(合計90秒以内目安)。モックなし。

対象:
  - petroleum_pooling                (石油プーリング, 双線形 濃度×流量)
  - foundry_charge_mix_multiperiod   (鋳造チャージ, 整数×連続 + 濃度×質量)
  - water_network_reuse              (用水再利用, 濃度×流量 + 凹費用)
"""
from __future__ import annotations

import math

import pytest

import petroleum_pooling
import foundry_charge_mix_multiperiod
import water_network_reuse


def _solve_small(build_model, time_limit=25.0):
    m = build_model("small")
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    return m


@pytest.mark.parametrize("mod", [
    petroleum_pooling,
    foundry_charge_mix_multiperiod,
    water_network_reuse,
], ids=["petroleum_pooling", "foundry_multiperiod", "water_network_reuse"])
def test_small_feasible_finite(mod):
    """small で実行可能解が出て目的値が有限であること。"""
    m = _solve_small(mod.build_model)
    assert m.getNSols() > 0, f"{mod.__name__}: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), f"{mod.__name__}: 目的値が非有限"
    # 目的値は最小化コスト(正)であるはず
    assert obj > 0.0


def test_scales_build():
    """3スケールすべて build できる(構造の健全性)。"""
    for mod in (petroleum_pooling, foundry_charge_mix_multiperiod,
                water_network_reuse):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0
            assert m.getNConss() > 0
