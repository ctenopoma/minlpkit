"""太陽光インバータ無効電力最適化 (Solar PV Inverter Reactive Power)

事業ストーリー
--------------
太陽光発電所群を束ねる「系統連系運用者」が、複数台のPVインバータについて、有効電力
(売電収益に直結)と無効電力(系統電圧維持のため系統運用者から要求される)の出力配分を
各時間帯で決める意思決定である。各インバータは皮相電力(有効電力と無効電力のベクトル和)
がインバータ定格容量を超えられないという非線形制約(P^2+Q^2 <= S_rated^2、円形の
出力可能領域)を持つ。系統運用者は各時間帯に発電所全体で満たすべき無効電力の目標値
(電圧調整のための系統要求)を課す。運用者は、各インバータの容量制約と系統全体の
無効電力要求を満たしながら、売電収益に直結する有効電力の合計を最大化する出力配分を
時間帯ごとに決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_inverter=3, n_period=3),
    "default": dict(n_inverter=4, n_period=4),
    "large": dict(n_inverter=6, n_period=5),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_inverter, n_period = cfg["n_inverter"], cfg["n_period"]
    inverters, periods = range(n_inverter), range(n_period)

    s_rated = {i: 10.0 + 2.0 * (i % 3) for i in inverters}  # インバータ定格皮相電力
    # 時間帯ごとの日射量に基づく有効電力上限(日中ピークを模した山型)
    irr_shape = [0.6, 0.9, 1.0, 0.85, 0.5]
    p_avail = {(i, t): s_rated[i] * irr_shape[t % len(irr_shape)] for i in inverters for t in periods}
    # 系統運用者が各時間帯に要求する無効電力の合計目標(電圧調整のため)
    q_target = {t: 3.0 + 0.5 * t for t in periods}

    model = Model("Solar_PV_Inverter")

    p = {(i, t): model.addVar(vtype="C", lb=0, ub=s_rated[i], name=f"p_{i}_{t}") for i in inverters for t in periods}
    q = {(i, t): model.addVar(vtype="C", lb=-s_rated[i], ub=s_rated[i], name=f"q_{i}_{t}")
         for i in inverters for t in periods}

    for i in inverters:
        for t in periods:
            # 皮相電力の円形容量制約(非線形): 有効・無効電力の出力可能領域
            model.addCons(p[i, t] * p[i, t] + q[i, t] * q[i, t] <= s_rated[i] ** 2, name=f"apparent_power_{i}_{t}")
            # 日射量による有効電力の上限
            model.addCons(p[i, t] <= p_avail[i, t], name=f"irradiance_cap_{i}_{t}")

    for t in periods:
        # 系統からの無効電力要求(発電所全体の合計で満たす)
        model.addCons(quicksum(q[i, t] for i in inverters) >= q_target[t], name=f"reactive_target_{t}")

    model.setObjective(quicksum(p[i, t] for i in inverters for t in periods), "maximize")
    model.data = {"p": p, "q": q, "dims": (n_inverter, n_period)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Max Active Power:", m.getObjVal())
