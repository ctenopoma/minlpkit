"""診断ルールエンジン evaluate の発火/非発火テスト(合成 metrics、ソルバー不要)。"""
from __future__ import annotations

import minlpkit as mk


def _ids(findings):
    return {f["id"] for f in findings}


def test_empty_metrics_no_findings():
    """観測量が無ければ何も発火しない。"""
    assert mk.evaluate({}) == []


def test_weak_relaxation_fires():
    """支配ボトルネックの強い相対違反 + 空間分枝多で weak_relaxation が発火。"""
    m = dict(bottleneck_rel_viol=0.8, spatial_share=0.5, bottleneck_type="nonlinear")
    fired = _ids(mk.evaluate(m))
    assert "weak_relaxation" in fired


def test_weak_relaxation_not_fires_when_spatial_low():
    """空間分枝寄与が閾値未満なら weak_relaxation は発火しない。"""
    m = dict(bottleneck_rel_viol=0.8, spatial_share=0.1)
    assert "weak_relaxation" not in _ids(mk.evaluate(m))


def test_symmetry_gate_by_sym_sound():
    """sym_sound=False(非線形で不確定)なら対称群が大きくても symmetry_info は発火しない。"""
    unsound = dict(sym_sound=False, largest_sym_group=5, n_sym_groups=2)
    assert "symmetry_info" not in _ids(mk.evaluate(unsound))
    sound = dict(sym_sound=True, largest_sym_group=5, n_sym_groups=2)
    assert "symmetry_info" in _ids(mk.evaluate(sound))


def test_numerical_scale_threshold():
    """残存係数比は真の悪条件(1e6)でのみ発火。自然なコスト差(1e3)では発火しない。"""
    benign = dict(residual_coef_ratio=1e3, residual_bigm_count=0)
    assert "numerical_scale" not in _ids(mk.evaluate(benign))
    ill = dict(residual_coef_ratio=1e7, residual_bigm_count=0)
    assert "numerical_scale" in _ids(mk.evaluate(ill))
    # 残存 Big-M が1件でもあれば発火
    bigm = dict(residual_coef_ratio=10, residual_bigm_count=2)
    assert "numerical_scale" in _ids(mk.evaluate(bigm))


def test_evaluate_sorted_by_severity():
    """発火結果は severity 昇順(critical→good)で返る。"""
    m = dict(bottleneck_rel_viol=0.8, spatial_share=0.5,   # weak_relaxation: serious
             sym_sound=True, largest_sym_group=5)          # symmetry_info: good
    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3}
    sev = [order[f["severity"]] for f in mk.evaluate(m)]
    assert sev == sorted(sev)
