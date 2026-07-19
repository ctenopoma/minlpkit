"""非凸関数の区分線形近似 (SOS2 vs Big-M) — SOS制約の実証用

非凸な1変数関数 f(x) を区分線形(PWL)近似して最小化する。
PWLは「隣接する2つの折れ点の凸結合」で表せる = 重み λ_k に SOS2(隣接2つまで非ゼロ)を課す。
これは Big-M(セグメントごとにバイナリ)を使わずに PWL を表現する方法。

    x = Σ_k λ_k·xk,  y = Σ_k λ_k·f(xk),  Σλ_k=1, λ>=0
    SOS2版:   λ に SOS2 制約(隣接2つまで非ゼロ)
    Big-M版:  セグメントのバイナリ z と λ_k <= z_{k-1}+z_k, Σz=1
"""

from __future__ import annotations

import math

from pyscipopt import Model, quicksum

X_LO, X_HI = 0.0, 10.0
N_BREAK = 21  # 折れ点数


def f(x: float) -> float:
    """非凸・多峰の目的関数。"""
    return math.sin(1.5 * x) + 0.15 * (x - 5.0) ** 2


def breakpoints() -> tuple[list[float], list[float]]:
    xs = [X_LO + (X_HI - X_LO) * k / (N_BREAK - 1) for k in range(N_BREAK)]
    return xs, [f(x) for x in xs]


def build_model(method: str = "sos2") -> Model:
    assert method in ("sos2", "bigm")
    xs, ys = breakpoints()
    K = len(xs)
    m = Model(f"pwl_{method}")
    lam = [m.addVar(lb=0, ub=1, name=f"lam_{k}") for k in range(K)]
    x = m.addVar(lb=X_LO, ub=X_HI, name="x")
    y = m.addVar(lb=-1e6, name="y")

    m.addCons(quicksum(lam) == 1, name="convex")
    m.addCons(x == quicksum(xs[k] * lam[k] for k in range(K)), name="x_def")
    m.addCons(y == quicksum(ys[k] * lam[k] for k in range(K)), name="y_def")

    if method == "sos2":
        m.addConsSOS2(lam, name="sos2_lambda")  # 隣接2つまで非ゼロ
    else:
        # Big-M(多重選択): セグメント s のバイナリ z_s、λ_k は隣接セグメントのみ有効
        z = [m.addVar(vtype="B", name=f"z_{s}") for s in range(K - 1)]
        m.addCons(quicksum(z) == 1, name="one_segment")
        for k in range(K):
            adj = []
            if k - 1 >= 0:
                adj.append(z[k - 1])
            if k <= K - 2:
                adj.append(z[k])
            m.addCons(lam[k] <= quicksum(adj), name=f"lam_seg_{k}")

    m.setObjective(y, "minimize")
    m.data = dict(x=x, y=y, lam=lam, xs=xs, ys=ys)
    return m


def main() -> None:
    # 真の最小(細かいグリッド)
    grid = [X_LO + (X_HI - X_LO) * i / 2000 for i in range(2001)]
    xstar = min(grid, key=f)
    print(f"真の最小: x*={xstar:.3f} f={f(xstar):.4f}")
    for method in ("sos2", "bigm"):
        m = build_model(method)
        m.hideOutput()
        m.optimize()
        print(f"{method:5s}: x={m.getVal(m.data['x']):.3f} y={m.getObjVal():.4f} "
              f"nodes={m.getNNodes()} status={m.getStatus()}")


if __name__ == "__main__":
    main()
