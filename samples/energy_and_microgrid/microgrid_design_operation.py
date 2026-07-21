"""マイクログリッド設計 + 複数代表日運用の同時決定 (Microgrid Design & Multi-Day Operation).

事業ストーリー
--------------
オフグリッド化を検討する工業団地の「マイクログリッド設計者」が、太陽光(PV)・
蓄電池・非常用発電機の設備容量(サイジング)と、季節を代表する複数の代表日
(夏平日・冬平日・中間期・週末など)にわたる充放電・出力配分(運用)を同時に決める
投資意思決定である。設備容量が運用の実行可能領域そのものを規定する(結合)ため、
容量を過小に見積もると特定の代表日で運用が破綻し、過大だと投資回収が悪化する。

各制約の業務的意味:
- **PV容量(連続、サイジング)**: 単位容量あたりの出力プロファイル(代表日×時刻の
  日射パターン)を容量に掛けた分だけ発電できる。容量が運用の発電上限を規定する。
- **蓄電池容量(連続、サイジング)+ 充放電損失(非線形)**: 蓄電池の内部抵抗損失は
  出力(C-rate)の2乗に比例し、容量が大きいほど同じ出力でも損失率は下がる
  (loss・cap ≥ k・p² という双曲線的関係。物理的には「電流~出力/電圧」「抵抗~1/容量」
  から損失~電流²・抵抗~出力²/容量となることに対応)。**容量という設計変数そのものが
  非線形項に現れる**ため、設計と運用が数式レベルで不可分に結合する。
- **発電機(整数、ユニット数)**: 非常用発電機は既製品の定格単位(例: 100kW機)を
  何台導入するかという整数決定であり、各代表日・各時刻でオンライン台数以下でしか
  出力できない(離散容量が運用上限を規定)。
- **代表日別の需給バランス**: 各代表日の各時刻で PV+蓄電池放電+発電機+系統購入
  (バックストップ、高コスト) = 需要 + 蓄電池充電。系統購入を許すことで常時実行可能。
- **代表日の重み付け(年間換算)**: 各代表日は年間の一定日数を代表しており、目的関数の
  運用費は重み(年間日数)で換算する。
- **蓄電池SOCダイナミクス(時間結合)**: 各代表日の中で残存エネルギー量(SOC)が
  充放電で変化し、代表日間は独立(1日で運用が完結する自己完結型の代表日)だが、
  日内では強い時間結合を持つ。

なぜ結合が業務要件として自然に入るか:
設備投資は一度決めれば数年〜十数年固定され、その後のあらゆる代表日の運用は
その容量の枠内でしか行えない。蓄電池の充放電損失が容量に反比例するという物理は
近似ではなく実際のセル内部抵抗の性質であり、容量(設計)と出力(運用)を同一の
非線形制約に同居させて初めて「大きく作るほど効率が良いが投資がかさむ」という
現実のトレードオフが表現される(容量と運用を分離すると、この非線形結合自体が
消えてしまう)。

scale ノブ(硬さの源泉: 統合意思決定(設備サイジング×多日運用の同時決定) + 物理結合
(蓄電池損失=出力²/容量の双曲線) + 時間結合(日内SOCダイナミクス)):
    small   : 代表日2 × 時刻6    (テスト・ハンズオン用。数分で最適)
    default : 代表日4 × 時刻14   (診断の題材。30秒でgap残存)
    large   : 代表日6 × 時刻24
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_day=2, n_period=6),
    "default": dict(n_day=4, n_period=14),
    "large":   dict(n_day=6, n_period=24),
}

COST_PV = 900.0          # 投資費[$/kW]
COST_BATT = 380.0        # 投資費[$/kWh]
COST_GEN_UNIT = 55000.0  # 発電機1台あたりの投資費[$]
GEN_UNIT_CAP = 120.0     # 発電機1台の定格出力[kW]
N_GEN_MAX = 4            # 導入可能な発電機台数の上限
FUEL_COST = 0.38         # 発電機の限界燃料費[$/kWh]
GRID_COST = 0.55         # 系統購入単価[$/kWh](バックストップ、高コスト)
BATT_K_LOSS = 0.22       # 蓄電池損失係数(出力²/容量に比例)
ETA_C, ETA_D = 0.96, 0.96  # 充放電効率(定格変換ロス、線形分)
MAX_CRATE = 0.5           # 蓄電池の最大C-rate(容量比の充放電出力上限)


def _data(scale: str):
    cfg = SCALES[scale]
    nDay, nT = cfg["n_day"], cfg["n_period"]
    rng = np.random.default_rng(20260724 + nDay * 41 + nT * 7)

    hours = np.linspace(6, 20, nT)  # 日中中心の代表時間帯
    # PV出力プロファイル(単位容量あたり、代表日ごとに晴天度が変わる)
    pv_peak = rng.uniform(0.65, 1.0, nDay)
    pv_profile = np.zeros((nDay, nT))
    for dday in range(nDay):
        shape = np.clip(np.sin(np.pi * (hours - 6) / 14.0), 0.0, None)
        pv_profile[dday] = pv_peak[dday] * shape

    # 需要プロファイル(代表日ごとに水準・形状が異なる=製造ラインの稼働パターン差)
    demand_level = rng.uniform(180.0, 320.0, nDay)
    demand = np.zeros((nDay, nT))
    for dday in range(nDay):
        shape = 0.55 + 0.45 * np.clip(np.sin(np.pi * (hours - 5) / 16.0), 0.0, None)
        noise = 1.0 + rng.uniform(-0.05, 0.05, nT)
        demand[dday] = demand_level[dday] * shape * noise

    # 代表日の年間換算重み(日数)
    day_weight = np.round(rng.uniform(50, 100, nDay))
    day_weight = day_weight / day_weight.sum() * 365.0

    return dict(nDay=nDay, nT=nT, pv_profile=pv_profile, demand=demand,
                day_weight=day_weight)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nDay, nT = d["nDay"], d["nT"]
    pv_profile, demand, day_weight = d["pv_profile"], d["demand"], d["day_weight"]

    m = Model("Microgrid_Design_Operation")
    DAY, T = range(nDay), range(nT)

    # --- 設計変数(サイジング。全代表日で共有=結合の源泉) ---
    cap_pv = m.addVar(vtype="C", lb=0.0, ub=1200.0, name="cap_pv")
    cap_batt = m.addVar(vtype="C", lb=5.0, ub=1500.0, name="cap_batt")
    n_gen = m.addVar(vtype="I", lb=0, ub=N_GEN_MAX, name="n_gen")

    # --- 運用変数(代表日×時刻) ---
    p_pv, p_gen, p_charge, p_discharge, p_grid, soc, loss = ({} for _ in range(7))
    z_gen = {}  # 発電機オンライン台数(整数、代表日×時刻で n_gen 以下)
    for dday in DAY:
        for t in T:
            p_pv[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"p_pv_{dday}_{t}")
            p_gen[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"p_gen_{dday}_{t}")
            z_gen[dday, t] = m.addVar(vtype="I", lb=0, ub=N_GEN_MAX, name=f"z_gen_{dday}_{t}")
            p_charge[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"p_charge_{dday}_{t}")
            p_discharge[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"p_discharge_{dday}_{t}")
            p_grid[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"p_grid_{dday}_{t}")
            loss[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"loss_{dday}_{t}")
        for t in range(nT + 1):
            soc[dday, t] = m.addVar(vtype="C", lb=0.0, name=f"soc_{dday}_{t}")

    for dday in DAY:
        # 日内SOCは代表日ごとに独立して自己完結(始点=終点、代表日間は結合しない)
        m.addCons(soc[dday, 0] == 0.5 * cap_batt, name=f"soc_init_{dday}")
        m.addCons(soc[dday, nT] >= 0.5 * cap_batt, name=f"soc_terminal_{dday}")

        for t in T:
            # 設計容量が運用上限を規定(結合)
            m.addCons(p_pv[dday, t] <= cap_pv * float(pv_profile[dday, t]),
                      name=f"pv_cap_{dday}_{t}")
            m.addCons(z_gen[dday, t] <= n_gen, name=f"gen_online_{dday}_{t}")
            m.addCons(p_gen[dday, t] <= GEN_UNIT_CAP * z_gen[dday, t], name=f"gen_cap_{dday}_{t}")
            m.addCons(p_charge[dday, t] <= MAX_CRATE * cap_batt, name=f"charge_rate_{dday}_{t}")
            m.addCons(p_discharge[dday, t] <= MAX_CRATE * cap_batt, name=f"discharge_rate_{dday}_{t}")
            m.addCons(soc[dday, t] <= cap_batt, name=f"soc_cap_{dday}_{t}")

            # 蓄電池の内部抵抗損失(非線形・双曲線): loss * cap_batt >= k * (p_charge + p_discharge)^2
            # 容量が大きいほど同じ出力でも損失率が下がる=設計変数が非線形項に現れる真の結合
            m.addCons(
                loss[dday, t] * cap_batt >= BATT_K_LOSS * (p_charge[dday, t] + p_discharge[dday, t])
                * (p_charge[dday, t] + p_discharge[dday, t]),
                name=f"batt_loss_{dday}_{t}")

            # SOCダイナミクス(充放電効率+内部抵抗損失を差し引く)
            m.addCons(
                soc[dday, t + 1] == soc[dday, t]
                + ETA_C * p_charge[dday, t] - p_discharge[dday, t] / ETA_D - loss[dday, t],
                name=f"soc_balance_{dday}_{t}")

            # 需給バランス(系統購入がバックストップ)
            m.addCons(
                p_pv[dday, t] + p_gen[dday, t] + p_discharge[dday, t] + p_grid[dday, t]
                == float(demand[dday, t]) + p_charge[dday, t],
                name=f"balance_{dday}_{t}")

    capex = COST_PV * cap_pv + COST_BATT * cap_batt + COST_GEN_UNIT * n_gen
    opex = quicksum(float(day_weight[dday]) * (
        FUEL_COST * p_gen[dday, t] + GRID_COST * p_grid[dday, t]
    ) for dday in DAY for t in T)
    m.setObjective(capex + opex, "minimize")

    m.data = dict(cap_pv=cap_pv, cap_batt=cap_batt, n_gen=n_gen, p_grid=p_grid,
                  scale=scale, dims=(nDay, nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
