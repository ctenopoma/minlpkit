"""McCormick 包絡の締まりの可視化 (Phase 2.a)

非凸な双線形項 z = x·y を、空間分枝限定法がどう凸緩和で挟み、
x の区間を分割するたびに緩和がどう締まるかをアニメーションで見せる。

McCormick 凸下界包絡(box [xL,xU]×[yL,yU] 上):
    w >= xL·y + x·yL − xL·yL
    w >= xU·y + x·yU − xU·yU
点ごとの下界は上記2平面の max。x 区間を k 分割し、各小区間の box で
包絡を張り直すと、緩和の最大ギャップは (Δx·Δy)/4 のオーダーで縮む。
これが spatial branching の「分割で緩和が締まる」核心。
"""

from __future__ import annotations

import numpy as np

Box = tuple[float, float, float, float]  # (xL, xU, yL, yU)


def piecewise_underestimator(xg: np.ndarray, yg: np.ndarray, box: Box, k: int) -> np.ndarray:
    """x を k 分割した区分McCormick凸下界を格子上で返す。shape=(len(yg), len(xg))。"""
    xL, xU, yL, yU = box
    edges = np.linspace(xL, xU, k + 1)
    W = np.empty((len(yg), len(xg)))
    for i, xv in enumerate(xg):
        idx = int(np.clip(np.searchsorted(edges, xv, side="right") - 1, 0, k - 1))
        a, b = edges[idx], edges[idx + 1]
        plane1 = a * yg + xv * yL - a * yL
        plane2 = b * yg + xv * yU - b * yU
        W[:, i] = np.maximum(plane1, plane2)
    return W


def true_surface(xg: np.ndarray, yg: np.ndarray) -> np.ndarray:
    return np.outer(yg, xg)  # z[j,i] = yg[j]*xg[i]


def max_gap(box: Box, k: int, nx: int = 80, ny: int = 60) -> float:
    xL, xU, yL, yU = box
    xg, yg = np.linspace(xL, xU, nx), np.linspace(yL, yU, ny)
    return float((true_surface(xg, yg) - piecewise_underestimator(xg, yg, box, k)).max())
