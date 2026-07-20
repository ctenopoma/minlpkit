"""Phase 13 T3 エネルギー計画(設計+運用の統合意思決定)クラスタ 3モデルの smoke テスト。

各モデルの ``build_model("small")`` が
  - 実行可能解を出し(nsols > 0)
  - 目的値が有限
であることを実SCIPで軽く確認する。モックなし。

対象:
  - transmission_expansion_operation (送電線増強×シナリオ別運用のdisjunctive結合)
  - microgrid_design_operation       (設備サイジング×多日運用、蓄電池損失の双曲線非線形)
  - hydrogen_hub_transport           (ハブ配置・容量×輸送・在庫、ベンダーズ分解適性)
"""
from __future__ import annotations

import math

import pytest

import transmission_expansion_operation
import microgrid_design_operation
import hydrogen_hub_transport


def _solve_small(build_model, time_limit=60.0):
    m = build_model("small")
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    return m


@pytest.mark.parametrize("mod", [
    transmission_expansion_operation,
    microgrid_design_operation,
    hydrogen_hub_transport,
], ids=["transmission_expansion_operation", "microgrid_design_operation",
        "hydrogen_hub_transport"])
def test_small_feasible_finite(mod):
    """small で実行可能解が出て目的値が有限であること。"""
    m = _solve_small(mod.build_model)
    assert m.getNSols() > 0, f"{mod.__name__}: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), f"{mod.__name__}: 目的値が非有限"
    assert obj >= 0.0


def test_scales_build():
    """3スケールすべて build できる(構造の健全性)。"""
    for mod in (transmission_expansion_operation, microgrid_design_operation,
                hydrogen_hub_transport):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0
            assert m.getNConss() > 0
