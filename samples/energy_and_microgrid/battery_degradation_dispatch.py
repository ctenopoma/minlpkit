"""サイクル劣化コストを内生化した蓄電池アービトラージ運用 (Battery Degradation-Aware Dispatch).

事業ストーリー
--------------
系統に連系したスタンドアロン蓄電池(BESS)の「運用者」が、電力市場の時間帯別価格
(卸/スポット価格)を見ながら充放電計画を立てる意思決定である。単純な価格差アービトラージ
(安い時に充電、高い時に放電)だけを追えば頻繁・急速な充放電ほど収益は増えるが、実際には
**サイクル劣化**(充放電のたびに電極が微小に劣化し、将来の使用可能容量が減る)という
将来コストが生じる。運用者はこの劣化コストを**内生化**し、目先の価格差収益と将来の
容量減少による経済損失を同時に最適化しなければならない。

各制約・非線形項の業務的意味(電気化学劣化研究の定性的傾向を単純化):
- **容量減衰(状態変数、時間結合1)**: 使用可能容量 `cap_t` は各期の劣化 `deg_t`
  (容量に対する減少率)だけ単調に減っていく状態変数。劣化は不可逆(在庫のように
  積み上がる)ため、早期の激しい運用は将来ずっと効いてくる。
- **Cレート `crate_t`(充放電速度/容量比)**: 高速な充放電ほど電極への機械的・化学的
  ストレスが大きく劣化が加速する。`crate_t * cap_t >= p_charge_t + p_discharge_t`
  という**容量を分母に持つ双曲線関係**(容量が減るほど同じ電力でもCレートが実質的に
  上がる=劣化がさらに加速する自己強化フィードバック)。
- **放電深度 `dod_t`(Depth of Discharge)**: 1期にどれだけ深く放電したかの比率
  (`dod_t * cap_t >= p_discharge_t`)。深い放電ほど電極結晶構造への負荷が大きく
  劣化が加速するという劣化研究の定性的知見を反映。
- **温度依存(データ由来の非線形係数)**: 外気温(季節・日内変動を持つ時系列データ)が
  高いほど電気化学反応が加速し劣化が指数的に増える(アレニウス則的傾向)という定性的
  事実を `exp(K_TEMP*(temp_t-TEMP_REF))` の期別係数として劣化式に掛け込む。
- **劣化速度の非線形結合(本モデルの核)**:
  `deg_t >= K_DEG * crate_t^1.5 * dod_t^1.3 * temp_factor_t`
  Cレート・DoD・温度が**掛け合わさって**劣化を加速させるという定性的傾向(単独の
  高Cレートより、高DoD・高温下での高Cレートの方がはるかに劣化が速い)を非線形の
  べき乗×積で単純化して表現した。
- **劣化コストの内生化(epigraph)**: 容量減少 `deg_t` は将来の代替設備投資費用の
  一部前借りとみなし、`deg_t * CAP_NOM * REPLACEMENT_COST` を目的関数に直接算入する
  (劣化コストが凸な下界として効く不等式なので epigraph 化は不要、`>=` で十分厳密)。
- **SOCダイナミクス(時間結合2)**: 充放電効率を通じた蓄電量(SOC)の推移。SOCの上限は
  その時点の(劣化後の)容量 `cap_t` そのもの=容量劣化がSOC可行領域を締め付ける。

なぜ「二重の時間結合」が業務要件として自然に入るか:
SOC(蓄電量)は各期の充放電で直接変化する短期の状態、容量 `cap_t` は劣化の蓄積で
不可逆に変化する長期の状態であり、両者は独立ではない——容量が減れば同じ電力入出力でも
Cレート・DoDが実質的に上がり劣化がさらに加速する(容量が痩せるほど痩せやすくなる)。
この相互依存は近似のための人工物ではなく、電気化学セルの物理(電流密度・電極面積の関係)
そのものであり、運用計画(いつ・どれだけ充放電するか)と資産の長期価値(将来何年使えるか)
を数式レベルで不可分にしている。

scale ノブ(硬さの源泉: 非線形結合(Cレート×DoD×温度のべき乗積、容量分母の双曲線) +
時間結合(SOC推移 + 劣化の不可逆累積という二重構造)):
    small   : 24期(1日, 1時間粒度)   (テスト・ハンズオン用。数分で実行可能解)
    default : 72期(3日, 1時間粒度)   (診断の題材。gap残存を是とする)
    large   : 168期(7日, 1時間粒度)
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_period=24),
    "default": dict(n_period=72),
    "large":   dict(n_period=168),
}

CAP_NOM = 1000.0            # 定格容量 [kWh]
CAP_MIN_FRAC = 0.5          # 劣化下限(この比率まで容量が落ちても運用は継続、これ未満は非現実)
MAX_CRATE_RATED = 1.0       # 定格Cレート上限(容量比の充放電電力上限)
ETA_C, ETA_D = 0.95, 0.95   # 充放電効率
REPLACEMENT_COST = 300.0    # 容量1kWh当たりの更新投資費 [$/kWh]
K_DEG = 2.0e-4              # 劣化速度係数
CRATE_EXP = 1.5             # Cレートのべき指数(高Cレートほど加速)
DOD_EXP = 1.3               # DoDのべき指数(深放電ほど加速)
TEMP_REF = 25.0             # 基準温度 [℃]
K_TEMP = 0.05                # 温度加速係数(アレニウス則的傾向の単純化)
SOC_TERMINAL_FRAC = 0.3      # 期末SOC下限(容量比)


def _data(scale: str):
    cfg = SCALES[scale]
    nT = cfg["n_period"]
    rng = np.random.default_rng(20260725 + nT * 13)

    hours = np.arange(nT) % 24
    day = np.arange(nT) // 24

    # 卸電力価格: 日内ピーク(夕方)+オフピーク(深夜)のスプレッド、日ごとにやや変動
    daily_mult = 1.0 + 0.10 * np.sin(2 * np.pi * day / max(1, (nT // 24) or 1) / 3.0 + 0.7)
    shape = 0.35 + 0.65 * np.clip(np.sin(np.pi * (hours - 6) / 15.0), 0.0, None)
    peak_bump = 0.55 * np.clip(1.0 - np.abs(hours - 19) / 4.0, 0.0, None)
    noise = 1.0 + rng.uniform(-0.05, 0.05, nT)
    price_buy = (0.06 + 0.28 * (shape + peak_bump)) * daily_mult * noise
    price_sell = price_buy * 0.85  # 小売買い/卸売り相当のスプレッド(往復無限アービトラージ防止)

    # 外気温(季節ドリフト+日内変動)[℃]
    season_base = 22.0 + 8.0 * np.sin(2 * np.pi * (np.arange(nT) / max(nT, 1)) * (nT / (24.0 * 30)) + 1.0)
    daily_temp = 6.0 * np.clip(np.sin(np.pi * (hours - 5) / 15.0), -0.3, 1.0)
    temp = season_base + daily_temp + rng.uniform(-1.0, 1.0, nT)
    temp_factor = np.exp(K_TEMP * (temp - TEMP_REF))

    return dict(nT=nT, price_buy=price_buy, price_sell=price_sell, temp_factor=temp_factor)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nT = d["nT"]
    price_buy, price_sell, temp_factor = d["price_buy"], d["price_sell"], d["temp_factor"]

    m = Model("Battery_Degradation_Dispatch")
    T, T1 = range(nT), range(nT + 1)

    # --- 状態変数(時間結合の2系統) ---
    cap = {t: m.addVar(vtype="C", lb=CAP_MIN_FRAC * CAP_NOM, ub=CAP_NOM, name=f"cap_{t}")
           for t in T1}
    soc = {t: m.addVar(vtype="C", lb=0.0, ub=CAP_NOM, name=f"soc_{t}") for t in T1}

    # --- 運用変数 ---
    p_charge, p_discharge, crate, dod, deg = ({} for _ in range(5))
    for t in T:
        p_charge[t] = m.addVar(vtype="C", lb=0.0, name=f"p_charge_{t}")
        p_discharge[t] = m.addVar(vtype="C", lb=0.0, name=f"p_discharge_{t}")
        crate[t] = m.addVar(vtype="C", lb=0.0, ub=2.5, name=f"crate_{t}")
        dod[t] = m.addVar(vtype="C", lb=0.0, ub=1.5, name=f"dod_{t}")
        deg[t] = m.addVar(vtype="C", lb=0.0, ub=0.05, name=f"deg_{t}")

    m.addCons(cap[0] == CAP_NOM, name="cap_init")
    m.addCons(soc[0] == 0.5 * CAP_NOM, name="soc_init")
    m.addCons(soc[nT] >= SOC_TERMINAL_FRAC * cap[nT], name="soc_terminal")

    for t in T:
        # 容量が運用上限を規定(劣化後の容量でしか充放電できない)
        m.addCons(p_charge[t] <= MAX_CRATE_RATED * cap[t], name=f"charge_cap_{t}")
        m.addCons(p_discharge[t] <= MAX_CRATE_RATED * cap[t], name=f"discharge_cap_{t}")
        m.addCons(soc[t] <= cap[t], name=f"soc_cap_{t}")

        # Cレート・DoD の定義(容量を分母に持つ双曲線=自己強化フィードバックの源泉)
        m.addCons(crate[t] * cap[t] >= p_charge[t] + p_discharge[t], name=f"crate_def_{t}")
        m.addCons(dod[t] * cap[t] >= p_discharge[t], name=f"dod_def_{t}")

        # 劣化速度: Cレート・DoD・温度の非線形結合(本モデルの核)
        m.addCons(
            deg[t] >= K_DEG * (crate[t] ** CRATE_EXP) * (dod[t] ** DOD_EXP) * float(temp_factor[t]),
            name=f"deg_def_{t}")

        # 容量劣化の累積(不可逆、時間結合その1)
        m.addCons(cap[t + 1] == cap[t] - deg[t] * CAP_NOM, name=f"cap_balance_{t}")

        # SOCダイナミクス(時間結合その2)
        m.addCons(
            soc[t + 1] == soc[t] + ETA_C * p_charge[t] - p_discharge[t] / ETA_D,
            name=f"soc_balance_{t}")

    arbitrage = quicksum(
        float(price_buy[t]) * p_charge[t] - float(price_sell[t]) * p_discharge[t] for t in T)
    degradation_cost = quicksum(deg[t] * CAP_NOM * REPLACEMENT_COST for t in T)
    m.setObjective(arbitrage + degradation_cost, "minimize")

    m.data = dict(cap=cap, soc=soc, p_charge=p_charge, p_discharge=p_discharge,
                  crate=crate, dod=dod, deg=deg, scale=scale, dims=(nT,))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")
        cap = m.data["cap"]
        nT = m.data["dims"][0]
        print(f"cap start->end: {m.getVal(cap[0]):.2f} -> {m.getVal(cap[nT]):.2f}")


if __name__ == "__main__":
    main()
