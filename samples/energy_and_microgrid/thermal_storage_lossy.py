"""槽外温度差の非線形熱損失を持つ蓄熱運用 (Thermal Storage with Nonlinear Ambient-Loss).

事業ストーリー
--------------
地域熱供給/工場蒸気系統に付随する複数の蓄熱槽(温水タンク)を運用する「蓄熱運用者」が、
電力料金の安い時間帯にヒートポンプで蓄熱し、熱需要ピーク時に放熱して賄う運用計画を
決める意思決定である。蓄熱槽は断熱されているとはいえ完全ではなく、**槽内外の温度差が
大きいほど自然対流的に熱損失が加速**するため、「早めに高温まで蓄熱して長く持たせる」
戦略は損失面で不利になる——いつ・どれだけ蓄熱するかという運用計画そのものが物理的な
損失構造と絡み合う。加えてヒートポンプの電力消費には**契約電力上限**があり、複数の
蓄熱槽は**共有のヒートポンプ熱出力容量**を取り合う。

各制約・非線形項の業務的意味:
- **槽温ダイナミクス(時間結合)**: 各槽の温度 `T_tank[j,t]` は熱容量 `TAU_j` を通じて
  「蓄熱 − 放熱 − 損失」の収支で決まる状態変数。今日の蓄熱判断が明日以降の可用エネルギー
  (放熱余力)を規定する。
- **自然対流損失(非線形、本モデルの核)**: 損失 `Loss_j,t >= UA_j * (T_tank_j,t -
  T_amb,t)^1.25` という、槽内外温度差のべき乗則(Newtonの冷却則の非線形拡張。
  自然対流では熱伝達係数自体が温度差に依存し、単純な線形則より損失が加速する)。
  外気温 `T_amb,t` は季節・日内変動する時系列データであり、温度差は運用(どこまで
  高温に蓄熱するか)と外生条件(気候)の両方に依存する。
- **COPの温度リフト依存(非線形・双線形、本モデルの核その2)**: ヒートポンプの成績係数
  (COP)は「汲み上げる温度差(リフト=槽温−外気温)」が大きいほど低下するという
  熱力学の定性的事実(カルノー効率の逆数的傾向を単純化)を反映し、
  `q_charge_j,t == (COP_MAX - K_COP * dtemp_j,t) * p_elec_j,t` という**槽温(状態変数)
  と電力消費(運用変数)の積**で結ばれる。損失項(温度差の凸なべき乗則)単体は
  スカラー凸なので分枝を要さないが、この COP×電力の積は真の双線形非凸であり、
  「高温に蓄熱するほど、その後の追い蓄熱の電力効率が落ちる」という二次的な
  ペナルティを通じて槽温状態と運用決定を数式レベルで結合し直す。
- **電力上限(契約制約、共有結合)**: ヒートポンプの電力消費は
  `Σ_j P_elec_j,t <= P_CONTRACT_LIMIT_t` という**全槽合計**の契約電力上限に縛られる
  (需要家側の契約デマンド=電力会社との契約容量)。1つの槽が電力を使い切ると他の槽が
  蓄熱できない、という真の資源競合。
- **共有ヒートポンプ容量(結合)**: 複数の蓄熱槽は`Σ_j Q_charge_j,t <= Q_HP_CAP`という
  **単一のヒートポンプ設備**の熱出力容量を取り合う(蓄熱槽ごとに専用ヒートポンプは
  持たず、共有設備を時間帯ごとに配分する現実の運用形態)。
- **熱需要充足(バックストップ付き)**: 各槽は割り当てられた熱需要家群の需要を満たす
  義務があり、蓄熱槽からの放熱で不足する分は高コストのバックアップボイラーで補う
  (常時実行可能性の担保)。

なぜ非線形の損失構造が業務要件として自然に入るか:
断熱材を通じた熱損失は近似ではなく熱力学そのもの(自然対流の熱伝達係数は温度差に
依存し、単純な線形比例則では過小評価される)であり、「早めにまとめて高温蓄熱する」
という一見合理的な戦略が損失面で不利になるというトレードオフを生む。これに契約電力
上限・共有ヒートポンプ容量という2つの横断制約が重なることで、単独の槽では自明な
充放熱計画が、複数槽の時間帯配分問題として真に結合する。

scale ノブ(硬さの源泉: 物理結合(温度差^1.25の非線形自然対流損失) + 統合結合
(契約電力上限・共有ヒートポンプ容量を複数槽が取り合う) + 時間結合(槽温ダイナミクス)):
    small   : 槽2 × 24期(1日, 1時間粒度)   (テスト・ハンズオン用。数分で実行可能解)
    default : 槽4 × 72期(3日, 1時間粒度)   (診断の題材。gap残存を是とする)
    large   : 槽6 × 168期(7日, 1時間粒度)
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_tank=2, n_period=24),
    "default": dict(n_tank=4, n_period=72),
    "large":   dict(n_tank=6, n_period=168),
}

T_MIN, T_MAX = 40.0, 95.0        # 槽内温度の物理上下限 [℃]
TAU = 22.0                        # 槽の熱容量 [kWh/℃](大きいほど同じ熱量での温度変化が小)
UA = 0.02                         # 自然対流損失係数
LOSS_EXP = 1.25                   # 損失のべき指数(自然対流の非線形拡張)
COP_MAX = 4.6                      # ヒートポンプの理論最大COP(リフト=0のとき)
K_COP = 0.020                      # COP低下係数(槽温-外気温=リフトが大きいほどCOPが下がる)
Q_CHARGE_MAX = 60.0                # 槽1つあたりの最大蓄熱速度 [kWth]
Q_DISCHARGE_MAX = 60.0             # 槽1つあたりの最大放熱速度 [kWth]
BACKUP_COST = 0.42                 # バックアップボイラーの限界燃料費 [$/kWh]
Q_HP_CAP = 140.0                   # 共有ヒートポンプの熱出力容量 [kWth](全槽合計の上限)
P_CONTRACT_LIMIT = 34.0            # 契約電力上限 [kWe](全槽合計の上限)


def _data(scale: str):
    cfg = SCALES[scale]
    nJ, nT = cfg["n_tank"], cfg["n_period"]
    rng = np.random.default_rng(20260726 + nJ * 97 + nT * 11)

    hours = np.arange(nT) % 24
    day = np.arange(nT) // 24

    # 外気温(冬季暖房シーズン想定。日中やや暖かく夜間冷え込む、日ごとに寒波が変動)
    day_drift = rng.uniform(-3.0, 3.0, max(1, nT // 24 + 1))
    day_drift_series = day_drift[day]
    T_amb = -1.0 + 6.0 * np.clip(np.sin(np.pi * (hours - 7) / 15.0), -0.5, 1.0) + day_drift_series
    T_amb += rng.uniform(-1.0, 1.0, nT)

    # 電力料金(夜間安・日中高の時間帯別)
    price_elec = 0.10 + 0.22 * np.clip(np.sin(np.pi * (hours - 8) / 13.0), 0.0, None)
    price_elec += rng.uniform(-0.01, 0.01, nT)

    # 槽ごとの熱需要(槽=需要家群単位で水準・ピーク時間帯が異なる=非一様データ)
    demand = np.zeros((nJ, nT))
    peak_hour = rng.uniform(6.0, 20.0, nJ)
    level = rng.uniform(18.0, 32.0, nJ)
    for j in range(nJ):
        shape = 0.30 + 0.70 * np.clip(1.0 - np.abs(hours - peak_hour[j]) / 7.0, 0.0, None)
        noise = 1.0 + rng.uniform(-0.06, 0.06, nT)
        demand[j] = level[j] * shape * noise

    return dict(nJ=nJ, nT=nT, T_amb=T_amb, price_elec=price_elec, demand=demand)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nJ, nT = d["nJ"], d["nT"]
    T_amb, price_elec, demand = d["T_amb"], d["price_elec"], d["demand"]

    m = Model("Thermal_Storage_Lossy")
    J, T, T1 = range(nJ), range(nT), range(nT + 1)

    T_tank = {(j, t): m.addVar(vtype="C", lb=T_MIN, ub=T_MAX, name=f"T_tank_{j}_{t}")
              for j in J for t in T1}
    dtemp, loss, q_charge, q_discharge, p_elec, q_backup = ({} for _ in range(6))
    for j in J:
        for t in T:
            dtemp[j, t] = m.addVar(vtype="C", lb=0.0, ub=T_MAX - min(float(T_amb.min()), 0.0),
                                    name=f"dtemp_{j}_{t}")
            loss[j, t] = m.addVar(vtype="C", lb=0.0, name=f"loss_{j}_{t}")
            q_charge[j, t] = m.addVar(vtype="C", lb=0.0, ub=Q_CHARGE_MAX, name=f"q_charge_{j}_{t}")
            q_discharge[j, t] = m.addVar(vtype="C", lb=0.0, ub=Q_DISCHARGE_MAX, name=f"q_discharge_{j}_{t}")
            p_elec[j, t] = m.addVar(vtype="C", lb=0.0, name=f"p_elec_{j}_{t}")
            q_backup[j, t] = m.addVar(vtype="C", lb=0.0, name=f"q_backup_{j}_{t}")

    for j in J:
        # 初期温度は下限寄り(運用開始時は満蓄していない)
        m.addCons(T_tank[j, 0] == T_MIN + 10.0, name=f"T_init_{j}")

        for t in T:
            # 槽内外温度差(変数、下限0で T_tank >= T_amb を暗に強制)
            m.addCons(dtemp[j, t] == T_tank[j, t] - float(T_amb[t]), name=f"dtemp_def_{j}_{t}")

            # 自然対流損失(非線形: 温度差のべき乗則、本モデルの核)
            m.addCons(loss[j, t] >= UA * (dtemp[j, t] ** LOSS_EXP), name=f"loss_def_{j}_{t}")

            # ヒートポンプ: 熱出力 = COP(リフト依存) * 電力入力(真の双線形、非凸)
            m.addCons(
                q_charge[j, t] == (COP_MAX - K_COP * dtemp[j, t]) * p_elec[j, t],
                name=f"hp_cop_{j}_{t}")

            # 槽温ダイナミクス(時間結合): 蓄熱 - 放熱 - 損失 を熱容量で温度変化に換算
            m.addCons(
                T_tank[j, t + 1] == T_tank[j, t]
                + (q_charge[j, t] - q_discharge[j, t] - loss[j, t]) / TAU,
                name=f"T_balance_{j}_{t}")

            # 熱需要充足(バックアップボイラーで常時実行可能性を担保)
            m.addCons(q_discharge[j, t] + q_backup[j, t] == float(demand[j, t]),
                      name=f"demand_{j}_{t}")

    for t in T:
        # 契約電力上限(全槽合計、共有結合)
        m.addCons(quicksum(p_elec[j, t] for j in J) <= P_CONTRACT_LIMIT, name=f"contract_power_{t}")
        # 共有ヒートポンプ熱出力容量(全槽合計、共有結合)
        m.addCons(quicksum(q_charge[j, t] for j in J) <= Q_HP_CAP, name=f"hp_capacity_{t}")

    elec_cost = quicksum(float(price_elec[t]) * p_elec[j, t] for j in J for t in T)
    backup_cost = quicksum(BACKUP_COST * q_backup[j, t] for j in J for t in T)
    m.setObjective(elec_cost + backup_cost, "minimize")

    m.data = dict(T_tank=T_tank, q_charge=q_charge, q_discharge=q_discharge,
                  p_elec=p_elec, q_backup=q_backup, scale=scale, dims=(nJ, nT))
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
