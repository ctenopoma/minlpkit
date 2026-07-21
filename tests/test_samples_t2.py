"""Phase 13 T2 エネルギー運用クラスタ 4モデルの smoke テスト。

各モデルの ``build_model("small")`` が
  - 実行可能解を出し(nsols > 0)
  - 目的値が有限
であることを実SCIPで軽く確認する。モックなし。

対象:
  - weekly_uc_ramp                    (週次UC + 簡易DC潮流のPTDF結合)
  - hydro_cascade_efficiency          (水頭依存効率=放流×貯水量の双線形カスケード)
  - gas_pipeline_weymouth             (Weymouth式 + コンプレッサ + ラインパック時間結合)
  - district_heating_detailed_physics (温度×流量の双線形ネットワーク、scale拡張)
"""
from __future__ import annotations

import math

import pytest

import weekly_uc_ramp
import hydro_cascade_efficiency
import gas_pipeline_weymouth
import district_heating_detailed_physics


def _solve_small(build_model, time_limit=60.0):
    m = build_model("small")
    m.hideOutput()
    m.setParam("limits/time", time_limit)
    m.optimize()
    return m


@pytest.mark.parametrize("mod", [
    weekly_uc_ramp,
    hydro_cascade_efficiency,
    gas_pipeline_weymouth,
    district_heating_detailed_physics,
], ids=["weekly_uc_ramp", "hydro_cascade_efficiency",
        "gas_pipeline_weymouth", "district_heating_detailed_physics"])
def test_small_feasible_finite(mod):
    """small で実行可能解が出て目的値が有限であること。"""
    m = _solve_small(mod.build_model)
    assert m.getNSols() > 0, f"{mod.__name__}: small で実行可能解なし"
    obj = m.getObjVal()
    assert math.isfinite(obj), f"{mod.__name__}: 目的値が非有限"
    assert obj >= 0.0


def test_scales_build():
    """3スケールすべて build できる(構造の健全性)。"""
    for mod in (weekly_uc_ramp, hydro_cascade_efficiency,
                gas_pipeline_weymouth, district_heating_detailed_physics):
        for sc in ("small", "default", "large"):
            m = mod.build_model(sc)
            assert m.getNVars() > 0
            assert m.getNConss() > 0
