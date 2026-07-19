"""minlpkit.gpu.cuopt_warmstart の実cuOptテスト。

WSL2 + cuOpt CLI が使える環境でのみ実行する(無い環境ではスキップ)。
gap_large の small スケールに cuOpt を短時間走らせ、得た解を SCIP へ注入 →
その後の SCIP 求解が cuOpt解以上(min化なので以下)の primal boundから始まることを確認する。
"""
from __future__ import annotations

import subprocess

import pytest
from gap_large import build_model

from minlpkit.gpu import cuopt_warmstart

_CUOPT_CMD = ["wsl", "-d", "Ubuntu", "--", "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"]


def _cuopt_available() -> bool:
    try:
        proc = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "test", "-x",
             "/home/ubuntu_dnn/cuopt-env/bin/cuopt_cli"],
            capture_output=True, timeout=30)
        return proc.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


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
