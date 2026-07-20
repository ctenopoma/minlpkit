"""Phase 13 T4 サプライチェーン統合クラスタ 3モデルの smoke テスト。

各モデルの ``build_model("small")`` が
  - 実行可能解を出し(nsols > 0)
  - 目的値が有限
であることを実SCIPで軽く確認する。モックなし。

対象:
  - production_distribution_integrated  (生産ロットサイジング×配送車両割当の統合)
  - multi_echelon_inventory_realistic   (工場→DC→小売、リードタイム跨ぎ+整数ロット)
  - maritime_inventory_routing_realistic (複数船舶の配船スケジュール×港湾在庫)
"""
from __future__ import annotations

import math

import pytest

import production_distribution_integrated
import multi_echelon_inventory_realistic
import maritime_inventory_routing_realistic


def _solve_small(build_model, time_limit=60.0):
    m = build_model("small")
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    return m


@pytest.mark.parametrize("mod", [
    production_distribution_integrated,
    multi_echelon_inventory_realistic,
    maritime_inventory_routing_realistic,
], ids=["production_distribution_integrated", "multi_echelon_inventory_realistic",
        "maritime_inventory_routing_realistic"])
def test_small_feasible_finite(mod):
    """small で実行可能解が出て目的値が有限であること。"""
    m = _solve_small(mod.build_model)
    assert m.getNSols() > 0, f"{mod.__name__}: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), f"{mod.__name__}: 目的値が非有限"
    assert obj >= 0.0


def test_scales_build():
    """3スケールすべて build できる(構造の健全性)。"""
    for mod in (production_distribution_integrated, multi_echelon_inventory_realistic,
                maritime_inventory_routing_realistic):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0
            assert m.getNConss() > 0
