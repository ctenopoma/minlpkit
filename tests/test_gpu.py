"""minlpkit.gpu.cuopt_warmstart の実cuOptテスト。

WSL2 + cuOpt CLI が使える環境でのみ実行する(無い環境ではスキップ)。
gap_large の small スケールに cuOpt を短時間走らせ、得た解を SCIP へ注入 →
その後の SCIP 求解が cuOpt解以上(min化なので以下)の primal boundから始まることを確認する。
"""
from __future__ import annotations

import pytest
from gap_large import build_model

from minlpkit.gpu import cuopt_available, cuopt_concurrent, cuopt_warmstart

_CUOPT_CMD = ["wsl", "-d", "Ubuntu", "--", "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]


def _cuopt_available() -> bool:
    return cuopt_available(_CUOPT_CMD)


def test_unavailable_env_raises_with_install_hint():
    """cuOpt未導入環境の挙動(GPU不要で常に実行): availabilityがFalseになり、
    warmstart呼び出しは導入案内付きRuntimeErrorになる(素のsubprocessエラーを出さない)。"""
    bogus = ["wsl", "-d", "Ubuntu", "--", "/nonexistent/cuopt_cli"]
    assert cuopt_available(bogus) is False
    m = build_model("small")
    with pytest.raises(RuntimeError, match="cuOpt が見つからない"):
        cuopt_warmstart(m, time_limit=1, cuopt_cmd=bogus)


@pytest.mark.skipif(not _cuopt_available(), reason="WSL2 cuOpt CLI が見つからない")
def test_cuopt_warmstart_injects_and_improves():
    m = build_model("small")
    res = cuopt_warmstart(m, time_limit=10, cuopt_cmd=_CUOPT_CMD)

    assert isinstance(res["objective"], float)
    assert res["accepted"] is True

    m.setParam("limits/time", 5)
    m.hideOutput()
    m.optimize()

    assert m.getNSols() > 0
    # min化なので、注入した解を起点に primal bound は cuOpt目的値以下(改善方向)であること
    assert m.getPrimalbound() <= res["objective"] + 1e-6


@pytest.mark.skipif(not _cuopt_available(), reason="WSL2 cuOpt CLI が見つからない")
def test_cuopt_concurrent_injects_during_solve():
    """常駐型: SCIP求解中にcuOptの解がイベントハンドラ経由で注入されること。

    SCIP側ヒューリスティクスをOFFにして「注入解だけがincumbent」の状況を作り、
    mid-solve注入の成立(inject_time > 0)と受理を確認する。
    """
    m = build_model("small")
    m.hideOutput()
    m.setHeuristics(3)  # SCIP_PARAMSETTING.OFF
    h = cuopt_concurrent(m, time_limit=10, cuopt_cmd=_CUOPT_CMD)
    m.setParam("limits/time", 40)
    m.optimize()
    info = h.result()

    assert info["injected"] is True
    assert isinstance(info["objective"], float)
    assert info["inject_time"] is not None and info["inject_time"] > 0
    assert m.getNSols() > 0
    assert m.getPrimalbound() <= info["objective"] + 1e-6
