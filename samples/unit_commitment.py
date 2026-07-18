"""プラント系 Unit Commitment (MINLP)

ユニットON/OFF(バイナリ) + 出力(連続)。
燃料費 = 二次コスト + バルブポイント効果 |e·sin(f·(pmin−p))| で非凸MINLPになる。
起動費・最小連続運転/停止・ランプ制約付き。

実行: uv run python samples/unit_commitment.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pyscipopt import Model, quicksum, sin

from minlpkit.transforms import perspective_quadratic

# ---- データ ----
# (pmin, pmax, a, b, c, e, f, startup_cost, ramp, min_up, min_down)
UNITS = {
    "U1": dict(pmin=100, pmax=400, a=500, b=10.0, c=0.010, e=120, f=0.060, su=800, ramp=120, mu=3, md=2),
    "U2": dict(pmin=80,  pmax=300, a=400, b=12.0, c=0.012, e=100, f=0.070, su=500, ramp=100, mu=2, md=2),
    "U3": dict(pmin=50,  pmax=200, a=300, b=14.0, c=0.015, e=80,  f=0.080, su=300, ramp=80,  mu=2, md=1),
    "U4": dict(pmin=30,  pmax=120, a=150, b=18.0, c=0.020, e=50,  f=0.090, su=100, ramp=120, mu=1, md=1),
}
DEMAND = [420, 450, 500, 620, 700, 760, 800, 780, 700, 600, 520, 460]
T = len(DEMAND)
RESERVE = 0.05  # 予備率


def build_model(perspective: bool = False) -> Model:
    """UC を構築する。

    perspective=False: ベースライン(素の凸二次下界 fc >= a·u + b·p + c·p^2)。
    perspective=True : 二次燃料費を perspective 再定式化
        (mk.perspective_quadratic ヘルパー経由。等価変換で最適値は不変)。
    """
    m = Model("plant_unit_commitment")

    u, v, w, p, fc, vp = {}, {}, {}, {}, {}, {}
    for i, d in UNITS.items():
        for t in range(T):
            u[i, t] = m.addVar(vtype="B", name=f"u_{i}_{t}")
            v[i, t] = m.addVar(vtype="B", name=f"v_{i}_{t}")  # 起動
            w[i, t] = m.addVar(vtype="B", name=f"w_{i}_{t}")  # 停止
            p[i, t] = m.addVar(lb=0, ub=d["pmax"], name=f"p_{i}_{t}")
            fc[i, t] = m.addVar(lb=0, name=f"fc_{i}_{t}")  # 二次燃料費
            vp[i, t] = m.addVar(lb=0, ub=d["e"], name=f"vp_{i}_{t}")  # バルブポイント費

    for i, d in UNITS.items():
        for t in range(T):
            # 出力範囲
            m.addCons(p[i, t] >= d["pmin"] * u[i, t])
            m.addCons(p[i, t] <= d["pmax"] * u[i, t])
            # 起動/停止ロジック (初期状態: 全ユニット停止)
            prev = u[i, t - 1] if t > 0 else 0
            m.addCons(v[i, t] - w[i, t] == u[i, t] - prev)
            m.addCons(v[i, t] + w[i, t] <= 1)
            # ランプ (起動時はpminへのジャンプを許可)
            if t > 0:
                m.addCons(p[i, t] - p[i, t - 1] <= d["ramp"] * u[i, t - 1] + d["pmin"] * v[i, t])
                m.addCons(p[i, t - 1] - p[i, t] <= d["ramp"] * u[i, t] + d["pmax"] * w[i, t])
            # 最小連続運転/停止
            for tau in range(t + 1, min(t + d["mu"], T)):
                m.addCons(u[i, tau] >= v[i, t])
            for tau in range(t + 1, min(t + d["md"], T)):
                m.addCons(u[i, tau] <= 1 - w[i, t])
            # 二次燃料費: fc >= a·u + b·p + c·p^2 (凸なので下界制約でOK)
            if perspective:
                # 二次項を perspective 化: c·p^2 <= (fc − a·u − b·p)·u(ヘルパー経由)
                perspective_quadratic(m, u[i, t], p[i, t], fc[i, t],
                                      d["a"], d["b"], d["c"], name=f"fc_persp_{i}_{t}")
            else:
                m.addCons(fc[i, t] >= d["a"] * u[i, t] + d["b"] * p[i, t] + d["c"] * p[i, t] * p[i, t])
            # バルブポイント: vp >= |e·sin(f·(pmin−p))| − e·(1−u)  (停止時は0を許可)
            s_expr = d["e"] * sin(d["f"] * (d["pmin"] - p[i, t]))
            m.addCons(vp[i, t] >= s_expr - d["e"] * (1 - u[i, t]))
            m.addCons(vp[i, t] >= -s_expr - d["e"] * (1 - u[i, t]))

    for t in range(T):
        # 需要と予備力
        m.addCons(quicksum(p[i, t] for i in UNITS) >= DEMAND[t])
        m.addCons(quicksum(UNITS[i]["pmax"] * u[i, t] for i in UNITS) >= DEMAND[t] * (1 + RESERVE))

    m.setObjective(
        quicksum(fc[i, t] + vp[i, t] + UNITS[i]["su"] * v[i, t] for i in UNITS for t in range(T)),
        "minimize",
    )
    m.data = dict(u=u, p=p)
    return m


def main() -> None:
    m = build_model()
    m.setParam("limits/time", 120)
    m.setParam("limits/gap", 0.01)
    m.optimize()

    print(f"\nstatus={m.getStatus()}  obj={m.getObjVal():,.1f}  gap={m.getGap() * 100:.2f}%  "
          f"nodes={m.getNNodes()}  time={m.getSolvingTime():.1f}s")
    u, p = m.data["u"], m.data["p"]
    print("\n     " + " ".join(f"t{t:02d}" for t in range(T)))
    for i in UNITS:
        row = " ".join(f"{m.getVal(p[i, t]):3.0f}" if m.getVal(u[i, t]) > 0.5 else "  -" for t in range(T))
        print(f"{i}: {row}")
    print("需要:" + " ".join(f"{d:3d}" for d in DEMAND))


if __name__ == "__main__":
    main()
