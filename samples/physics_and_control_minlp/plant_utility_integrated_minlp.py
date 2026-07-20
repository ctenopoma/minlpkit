"""統合ユーティリティプラント: 熱源・熱交換器・搬送ポンプ・成層蓄熱・蓄電池の連成運用 (MINLP).

事業ストーリー
--------------
地域熱供給/大規模工場のユーティリティプラントの「運転計画担当者」が、1日の各時間帯について
「どの熱源機(空気熱源ヒートポンプ)を何台・どれだけ動かすか」「一次側/二次側の搬送ポンプを
何%の回転数で回すか」「熱交換器の両端温度をどこに置くか」「蓄熱槽に貯めるか取り崩すか」
「蓄電池を充放電するか」を**同時に**決める意思決定である。

この5要素は現場では別々の担当・別々の制御盤に分かれているが、物理的には一本の水路と
一本の電路で繋がっており、独立に最適化すると必ず損をする。本モデルはその連成を
数式レベルで表現する。

各制約・非線形項の業務的意味:
- **熱源機のCOPと外気温(双線形 + データ依存デレート)**: 空気熱源ヒートポンプの成績係数は
  汲み上げ温度差(リフト = 送水温度 T_hot − 外気温)が大きいほど低下する。供給熱量は
  `q_hp == (COP_MAX − K_LIFT*lift) * p_hp` という **送水温度(状態変数)と消費電力(運用変数)の積**
  で決まる真の双線形。さらに寒冷時は空気密度・着霜により**最大能力そのものが低下**するため、
  外気温時系列から算出した係数で定格能力をデレートする(能力とCOPが同時に悪化する二重苦)。
- **熱交換器の対数平均温度差 LMTD(対数項、本モデルの核その1)**: 一次側(プラント側)と
  二次側(配管網側)を分離する向流熱交換器の伝熱量は
  `q_hx == U*A * (dt1 − dt2) / ln(dt1/dt2)` で決まる。これは伝熱工学の厳密式であり、
  算術平均温度差での代用は高ΔT比で誤差が大きい。両端温度差 dt1/dt2 はいずれも決定変数
  なので、**対数を含む非凸等式**が入る(既存の熱交換サンプルが算術平均で回避していた項)。
- **一次流量 < 二次流量(低流量・大温度差運転)**: 一次側を絞って大きな温度差で送るのが
  近年の地域熱供給の標準設計。`m_p <= FLOW_RATIO*m_s` を課すと、熱収支から
  `dt1 − dt2 = q/cp * (1/m_p − 1/m_s) > 0` が自動的に従うため、LMTD の対数が
  dt1 = dt2 の可除特異点に落ちない(数値的健全性が物理的設計方針から導かれる)。
- **ポンプの相似則とBEP効率(3乗項、本モデルの核その2)**: インバータ制御ポンプは
  回転数比 n に対し **流量 Q ∝ n、揚程 H ∝ n²、水動力 ∝ n³**(相似則)。さらに実機の
  効率は最高効率点(BEP)から離れるほど落ちるため `eta(n) = ETA_BEP − K_BEP*(n − N_BEP)²`。
  軸動力は `w_pump * eta(n) == P_HYD_RATED * n³` という**3次/2次の有理式**で決まる。
  「流量を2割増やすと搬送動力は約1.7倍」という非線形ペナルティが、熱交換器の温度差設定
  (流量を増やせば温度差は縮むが動力は3乗で増える)と正面からぶつかる。
- **成層蓄熱槽(層別温度、本モデルの核その3)**: 蓄熱槽を上下 nL 層に分割し、各層の温度
  `T_lay[l,t]` を状態変数とする。蓄熱時は上層から高温水が入り下方へ、放熱時は下層から
  低温水が入り上方へカスケードする(風上差分)。層間の移流項は `cp*m*(T_上流 − T_自層)`
  という**流量×温度の双線形**であり、単一ノードのエネルギーSOCモデルでは表現できない
  「温度成層が崩れると高温水が取り出せなくなる」という運用上の失敗が再現される。
  各層は外気との温度差に比例した放熱損失と、層間熱伝導(成層の崩壊)を持つ。
- **蓄電池のサイクル劣化(容量分母の双曲線 + べき乗積)**: 熱源機とポンプの電力を
  時間帯別料金の中で賄うため蓄電池を併設する。劣化は
  `deg >= K_DEG * crate^1.5 * dod^1.3` として内生化し、目先の電力費削減と将来の
  容量減少を同時に評価する(`battery_degradation_dispatch` と同じ定式化を再利用)。
- **需要充足(バックストップ付き)**: 熱需要は「二次側直送 + 蓄熱槽からの放熱 +
  バックアップボイラー」で満たす。ボイラーと系統購入電力が常に利用可能なため
  常時実行可能だが、いずれも高コストなので最適解には現れにくい。

なぜ5要素の連成が業務要件として自然に入るか:
送水温度 T_hot を上げれば熱交換器の温度差が稼げて流量(=搬送動力)を減らせるが、
ヒートポンプのリフトが増えてCOPが落ちる。流量を増やせばCOPは守れるが搬送動力が
3乗で効いてくる。蓄熱槽に貯めれば安価な夜間電力を使えるが、高温で貯めるほど
放熱損失と成層崩壊が進む。蓄電池を使えば電力単価を平準化できるが劣化する——
これらはすべて**同じ水と同じ電気**を巡るトレードオフであり、要素ごとに分けて
最適化すると各要素の最適が全体の最適から系統的にずれる。

scale ノブ(硬さの源泉: 物理結合(LMTD対数・ポンプ3乗有理式・COP双線形・成層の移流双線形)
+ 統合結合(熱源×熱交換×搬送×蓄熱×蓄電が単一の熱収支と電力収支で結ばれる)
+ 時間結合(層別槽温ダイナミクス + 蓄電池の二重状態) + 離散(熱源機の起動停止)):
    small   : 熱源2台 × 6期 × 3層    (テスト・ハンズオン用。実測: 120秒で gap 約20%)
    default : 熱源2台 × 12期 × 3層   (診断の題材。gap残存を是とする)
    large   : 熱源3台 × 24期 × 4層

注意: 対数(LMTD)・3次有理式(ポンプ)・多数の双線形(COP/混合/成層移流)が同居するため、
`ac_opf` と同様に **small でも最適性証明は現実的でない**。受け入れ基準は「実行可能解が
出て目的値が有限」であり、gap は残る前提で診断・改善の題材として使う。
なお LMTD の対数等式は、幾何平均/算術平均による挟み込み(下記 hx_lmtd_lb/ub)と
変数境界の事前縮約を入れないと双対境界がまったく締まらない(実測: 69% → 21%)。
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, log, quicksum

SCALES = {
    "small":   dict(n_hp=2, n_period=6,  n_layer=3),
    "default": dict(n_hp=2, n_period=12, n_layer=3),
    "large":   dict(n_hp=3, n_period=24, n_layer=4),
}

CP = 4.19                    # 水の比熱 [kJ/(kg·K)] → cp*m[kg/s]*dT[K] = 熱流[kW]
DT_H = 1.0                   # 1期の長さ [h]

# --- 熱源機(空気熱源ヒートポンプ) ---
COP_MAX = 5.5                # リフト0における理論上限COP
K_LIFT = 0.035               # リフト1KあたりのCOP低下
Q_HP_MAX = 300.0             # 1台の定格熱出力 [kWth](外気温でデレートされる)
Q_HP_MIN_FRAC = 0.35         # 起動時の最低負荷率(部分負荷下限)
P_HP_MAX = 110.0             # 1台の最大消費電力 [kWe]
DERATE_PER_K = 0.012         # 外気温が基準を下回る1Kあたりの能力低下率
T_DERATE_REF = 7.0           # 能力デレートの基準外気温 [℃]

# --- 熱交換器(向流、一次/二次分離) ---
UA_HX = 55.0                 # 総括伝熱係数×伝熱面積 [kW/K]
DT_APPROACH_MIN = 3.0        # 両端の最小アプローチ温度差 [K]
LMTD_GAP = 0.5               # dt1 − dt2 の下限 [K](対数の可除特異点を避ける数値的安全弁)
FLOW_RATIO = 0.85            # 一次流量/二次流量の上限(低流量・大温度差運転)

# --- 温度の物理上下限 [℃] ---
T_HOT_MIN, T_HOT_MAX = 62.0, 92.0     # 一次側 熱交換器入口(熱源機の送水温度)
T_PRET_MIN, T_PRET_MAX = 42.0, 82.0   # 一次側 熱交換器出口(熱源機への戻り)
T_SSUP_MIN, T_SSUP_MAX = 55.0, 86.0   # 二次側 熱交換器出口(配管網への送水)
T_CRET_MIN, T_CRET_MAX = 38.0, 72.0   # 二次側 熱交換器入口(混合戻り温度)
T_SRET = 45.0                          # 需要家からの戻り温度 [℃](設計値、固定)
T_LAY_MIN, T_LAY_MAX = 40.0, 90.0     # 蓄熱槽 各層の温度

# --- 搬送ポンプ(インバータ制御、相似則 + BEP効率) ---
N_SPEED_MIN, N_SPEED_MAX = 0.30, 1.0  # 回転数比の可変範囲
M_P_RATED = 8.0              # 一次ポンプ定格流量 [kg/s]
M_S_RATED = 13.0             # 二次ポンプ定格流量 [kg/s]
P_HYD_P_RATED = 9.0          # 一次ポンプ定格水動力 [kW]
P_HYD_S_RATED = 34.0         # 二次ポンプ定格水動力 [kW]
ETA_BEP = 0.78               # 最高効率点における効率
N_BEP = 0.80                 # 最高効率点の回転数比
K_BEP = 0.45                 # BEPから外れたときの効率低下係数

# --- 成層蓄熱槽 ---
C_LAYER = 39.0               # 1層の熱容量 [kWh/K]
UA_LAYER = 0.15              # 1層の外気放熱係数 [kW/K]
K_COND = 0.8                 # 層間熱伝導係数 [kW/K](成層の崩壊)
M_TANK_MAX = 6.0             # 蓄熱/放熱の最大流量 [kg/s]

# --- 蓄電池(劣化内生化) ---
CAP_NOM = 400.0              # 定格容量 [kWh]
CAP_MIN_FRAC = 0.7           # 計画期間内の容量下限(容量比)
P_BATT_MAX = 200.0           # 最大充放電電力 [kW]
ETA_C, ETA_D = 0.95, 0.95    # 充放電効率
REPLACEMENT_COST = 300.0     # 容量1kWhあたりの更新投資費 [$/kWh]
K_DEG = 2.0e-4               # 劣化速度係数
CRATE_EXP, DOD_EXP = 1.5, 1.3
SOC_TERMINAL_FRAC = 0.4      # 期末SOC下限(容量比)

# --- コスト ---
BOILER_COST = 0.085          # バックアップボイラーの限界燃料費 [$/kWhth]


def _data(scale: str):
    cfg = SCALES[scale]
    nK, nT, nL = cfg["n_hp"], cfg["n_period"], cfg["n_layer"]
    rng = np.random.default_rng(20260727 + nK * 53 + nT * 17 + nL * 7)

    # 24時間周期の中から nT 期を等間隔に切り出す(小規模scaleでも日内変動を保つ)
    hours = np.linspace(0.0, 24.0, nT, endpoint=False)

    # 外気温 [℃](冬季。明け方に冷え込み、日中やや緩む)
    T_amb = 1.5 + 7.0 * np.clip(np.sin(np.pi * (hours - 7.0) / 15.0), -0.6, 1.0)
    T_amb += rng.uniform(-1.2, 1.2, nT)

    # 電力料金 [$/kWh](夜間安・夕方ピークの時間帯別)
    base = 0.11 + 0.14 * np.clip(np.sin(np.pi * (hours - 7.0) / 14.0), 0.0, None)
    peak = 0.13 * np.clip(1.0 - np.abs(hours - 18.0) / 3.5, 0.0, None)
    price_elec = base + peak + rng.uniform(-0.006, 0.006, nT)

    # 熱需要 [kWth](朝と夕方の二山。外気が冷えるほど増える)
    shape = (0.55
             + 0.45 * np.clip(1.0 - np.abs(hours - 7.5) / 4.0, 0.0, None)
             + 0.50 * np.clip(1.0 - np.abs(hours - 19.0) / 4.5, 0.0, None))
    weather = 1.0 + 0.030 * (8.0 - T_amb)
    demand = 430.0 * shape * weather * (1.0 + rng.uniform(-0.04, 0.04, nT))

    # 熱源機の能力デレート係数(外気温が T_DERATE_REF を下回るほど能力が落ちる)
    derate = np.clip(1.0 - DERATE_PER_K * np.clip(T_DERATE_REF - T_amb, 0.0, None), 0.55, 1.0)

    return dict(nK=nK, nT=nT, nL=nL, T_amb=T_amb, price_elec=price_elec,
                demand=demand, derate=derate)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nK, nT, nL = d["nK"], d["nT"], d["nL"]
    T_amb, price_elec, demand, derate = d["T_amb"], d["price_elec"], d["demand"], d["derate"]

    m = Model("Plant_Utility_Integrated")
    K, T, T1, L = range(nK), range(nT), range(nT + 1), range(nL)

    # ================= 変数 =================
    # --- 熱源機 ---
    z_hp, p_hp, q_hp = {}, {}, {}
    for k in K:
        for t in T:
            z_hp[k, t] = m.addVar(vtype="B", name=f"z_hp_{k}_{t}")
            p_hp[k, t] = m.addVar(vtype="C", lb=0.0, ub=P_HP_MAX, name=f"p_hp_{k}_{t}")
            q_hp[k, t] = m.addVar(vtype="C", lb=0.0, ub=Q_HP_MAX, name=f"q_hp_{k}_{t}")

    # --- 一次/二次の温度と熱交換器 ---
    # 変数上限は物理から詰めておく。空間分枝限定法の緩和強度は変数境界の広さに直結し、
    # とくに対数・双線形項は緩い境界のまま放置すると双対境界がまったく締まらない。
    #   q_hx <= 熱源機の総定格 → lmtd = q_hx/UA <= LMTD_UB
    #   幾何平均の不等式 dt1*dt2 <= lmtd^2 と dt2 >= DT_APPROACH_MIN から dt1 の上限
    LMTD_UB = min(60.0, nK * Q_HP_MAX / UA_HX)
    DT1_UB = min(T_HOT_MAX - T_SSUP_MIN, LMTD_UB * LMTD_UB / DT_APPROACH_MIN)
    DT2_UB = min(T_PRET_MAX - T_CRET_MIN, LMTD_UB)

    T_hot, T_pret, T_ssup, T_cret = {}, {}, {}, {}
    dt1, dt2, lmtd, q_hx = {}, {}, {}, {}
    for t in T:
        T_hot[t] = m.addVar(vtype="C", lb=T_HOT_MIN, ub=T_HOT_MAX, name=f"T_hot_{t}")
        T_pret[t] = m.addVar(vtype="C", lb=T_PRET_MIN, ub=T_PRET_MAX, name=f"T_pret_{t}")
        T_ssup[t] = m.addVar(vtype="C", lb=T_SSUP_MIN, ub=T_SSUP_MAX, name=f"T_ssup_{t}")
        T_cret[t] = m.addVar(vtype="C", lb=T_CRET_MIN, ub=T_CRET_MAX, name=f"T_cret_{t}")
        # dt1: 高温端アプローチ(一次入口 − 二次出口), dt2: 低温端アプローチ(一次出口 − 二次入口)
        dt1[t] = m.addVar(vtype="C", lb=DT_APPROACH_MIN + LMTD_GAP, ub=DT1_UB, name=f"dt1_{t}")
        dt2[t] = m.addVar(vtype="C", lb=DT_APPROACH_MIN, ub=DT2_UB, name=f"dt2_{t}")
        lmtd[t] = m.addVar(vtype="C", lb=DT_APPROACH_MIN, ub=LMTD_UB, name=f"lmtd_{t}")
        q_hx[t] = m.addVar(vtype="C", lb=0.0, ub=nK * Q_HP_MAX, name=f"q_hx_{t}")

    # --- ポンプ(回転数比・流量・軸動力) ---
    # 軸動力の上限は n=1(定格)のときの n³/eta(n) で決まる(相似則より n³ は単調増加、
    # eta は N_BEP から離れるほど下がるので、可変域の端で評価すれば厳密な上限になる)
    _eta_at = lambda n: ETA_BEP - K_BEP * (n - N_BEP) ** 2
    _pump_ub = lambda rated: rated * max(
        n ** 3 / _eta_at(n) for n in (N_SPEED_MIN, N_BEP, N_SPEED_MAX))
    W_P_UB, W_S_UB = _pump_ub(P_HYD_P_RATED), _pump_ub(P_HYD_S_RATED)

    n_p, n_s, m_p, m_s, w_p, w_s = ({} for _ in range(6))
    for t in T:
        n_p[t] = m.addVar(vtype="C", lb=N_SPEED_MIN, ub=N_SPEED_MAX, name=f"n_p_{t}")
        n_s[t] = m.addVar(vtype="C", lb=N_SPEED_MIN, ub=N_SPEED_MAX, name=f"n_s_{t}")
        m_p[t] = m.addVar(vtype="C", lb=0.0, ub=M_P_RATED, name=f"m_p_{t}")
        m_s[t] = m.addVar(vtype="C", lb=0.0, ub=M_S_RATED, name=f"m_s_{t}")
        w_p[t] = m.addVar(vtype="C", lb=0.0, ub=W_P_UB, name=f"w_p_{t}")
        w_s[t] = m.addVar(vtype="C", lb=0.0, ub=W_S_UB, name=f"w_s_{t}")

    # --- 成層蓄熱槽 ---
    T_lay = {(l, t): m.addVar(vtype="C", lb=T_LAY_MIN, ub=T_LAY_MAX, name=f"T_lay_{l}_{t}")
             for l in L for t in T1}
    m_chg, m_dis, m_direct, q_boiler = {}, {}, {}, {}
    for t in T:
        m_chg[t] = m.addVar(vtype="C", lb=0.0, ub=M_TANK_MAX, name=f"m_chg_{t}")
        m_dis[t] = m.addVar(vtype="C", lb=0.0, ub=M_TANK_MAX, name=f"m_dis_{t}")
        m_direct[t] = m.addVar(vtype="C", lb=0.0, ub=M_S_RATED, name=f"m_direct_{t}")
        q_boiler[t] = m.addVar(vtype="C", lb=0.0, name=f"q_boiler_{t}")

    # --- 蓄電池 ---
    cap = {t: m.addVar(vtype="C", lb=CAP_MIN_FRAC * CAP_NOM, ub=CAP_NOM, name=f"cap_{t}")
           for t in T1}
    soc = {t: m.addVar(vtype="C", lb=0.0, ub=CAP_NOM, name=f"soc_{t}") for t in T1}
    p_chg, p_dis, crate, dod, deg, p_grid = ({} for _ in range(6))
    for t in T:
        p_chg[t] = m.addVar(vtype="C", lb=0.0, ub=P_BATT_MAX, name=f"p_chg_{t}")
        p_dis[t] = m.addVar(vtype="C", lb=0.0, ub=P_BATT_MAX, name=f"p_dis_{t}")
        crate[t] = m.addVar(vtype="C", lb=0.0, ub=2.0, name=f"crate_{t}")
        dod[t] = m.addVar(vtype="C", lb=0.0, ub=1.5, name=f"dod_{t}")
        deg[t] = m.addVar(vtype="C", lb=0.0, ub=0.05, name=f"deg_{t}")
        # 系統購入の上限も明示(電力収支の右辺が取りうる最大値。緩和を締めるため)
        p_grid[t] = m.addVar(vtype="C", lb=0.0,
                             ub=nK * P_HP_MAX + W_P_UB + W_S_UB + P_BATT_MAX,
                             name=f"p_grid_{t}")

    # ================= 制約 =================
    for t in T:
        amb = float(T_amb[t])

        # ---- 熱源機: リフト依存COP(双線形) + 外気温デレート ----
        for k in K:
            # 供給熱量 = COP(リフト) × 消費電力。リフト = 送水温度 − 外気温(送水温度は決定変数)
            m.addCons(
                q_hp[k, t] == (COP_MAX - K_LIFT * (T_hot[t] - amb)) * p_hp[k, t],
                name=f"hp_cop_{k}_{t}")
            # 外気温デレート後の定格能力が上限(起動しているときのみ)
            m.addCons(q_hp[k, t] <= Q_HP_MAX * float(derate[t]) * z_hp[k, t],
                      name=f"hp_cap_{k}_{t}")
            # 部分負荷下限(起動したら最低負荷は出す)
            m.addCons(q_hp[k, t] >= Q_HP_MIN_FRAC * Q_HP_MAX * float(derate[t]) * z_hp[k, t],
                      name=f"hp_minload_{k}_{t}")
            m.addCons(p_hp[k, t] <= P_HP_MAX * z_hp[k, t], name=f"hp_pmax_{k}_{t}")
        # ベース熱源として最低1台は運転(熱交換器を常に通水させ、LMTDの退化を防ぐ)
        m.addCons(quicksum(z_hp[k, t] for k in K) >= 1, name=f"hp_base_{t}")

        # ---- ポンプ: 相似則(Q∝n, 水動力∝n³) + BEP効率(3次/2次の有理式) ----
        m.addCons(m_p[t] == M_P_RATED * n_p[t], name=f"pump_p_flow_{t}")
        m.addCons(m_s[t] == M_S_RATED * n_s[t], name=f"pump_s_flow_{t}")
        m.addCons(
            w_p[t] * (ETA_BEP - K_BEP * (n_p[t] - N_BEP) * (n_p[t] - N_BEP))
            == P_HYD_P_RATED * n_p[t] * n_p[t] * n_p[t],
            name=f"pump_p_power_{t}")
        m.addCons(
            w_s[t] * (ETA_BEP - K_BEP * (n_s[t] - N_BEP) * (n_s[t] - N_BEP))
            == P_HYD_S_RATED * n_s[t] * n_s[t] * n_s[t],
            name=f"pump_s_power_{t}")
        # 低流量・大温度差運転(この設計方針が dt1 > dt2 を保証しLMTDの対数を健全化する)
        m.addCons(m_p[t] <= FLOW_RATIO * m_s[t], name=f"primary_low_flow_{t}")

        # ---- 熱交換器: 熱収支(双線形) + LMTD(対数) ----
        m.addCons(q_hx[t] == quicksum(q_hp[k, t] for k in K), name=f"hx_source_{t}")
        m.addCons(q_hx[t] == CP * m_p[t] * (T_hot[t] - T_pret[t]), name=f"hx_primary_{t}")
        m.addCons(q_hx[t] == CP * m_s[t] * (T_ssup[t] - T_cret[t]), name=f"hx_secondary_{t}")
        m.addCons(dt1[t] == T_hot[t] - T_ssup[t], name=f"hx_dt1_{t}")
        m.addCons(dt2[t] == T_pret[t] - T_cret[t], name=f"hx_dt2_{t}")
        m.addCons(dt1[t] >= dt2[t] + LMTD_GAP, name=f"hx_dt_order_{t}")
        # 対数平均温度差(厳密式)。dt1 > dt2 が上で保証されるため log は well-defined
        m.addCons(lmtd[t] * (log(dt1[t]) - log(dt2[t])) == dt1[t] - dt2[t], name=f"hx_lmtd_{t}")
        # 対数平均は幾何平均以上・算術平均以下という古典的な不等式(冗長だが妥当な切除平面)。
        # 対数を含む等式の緩和は空間分枝限定法では非常に緩いため、この2本を明示的に
        # 与えるだけで LMTD の双対境界が劇的に締まる。
        m.addCons(lmtd[t] <= 0.5 * (dt1[t] + dt2[t]), name=f"hx_lmtd_ub_{t}")
        m.addCons(lmtd[t] * lmtd[t] >= dt1[t] * dt2[t], name=f"hx_lmtd_lb_{t}")
        m.addCons(q_hx[t] == UA_HX * lmtd[t], name=f"hx_rate_{t}")

        # ---- 二次側の流量配分と混合戻り温度 ----
        # 二次送水 m_s は「需要家への直送 m_direct」と「蓄熱槽への蓄熱 m_chg」に分かれる
        m.addCons(m_s[t] == m_direct[t] + m_chg[t], name=f"sec_split_{t}")
        # 熱交換器への戻りは「需要家戻り(T_SRET)」と「槽下層からの戻り」の混合(双線形)
        m.addCons(
            m_s[t] * T_cret[t] == m_direct[t] * T_SRET + m_chg[t] * T_lay[nL - 1, t],
            name=f"sec_mix_{t}")

        # ---- 熱需要充足(直送 + 槽からの放熱 + バックアップボイラー) ----
        m.addCons(
            CP * m_direct[t] * (T_ssup[t] - T_SRET)
            + CP * m_dis[t] * (T_lay[0, t] - T_SRET)
            + q_boiler[t] == float(demand[t]),
            name=f"heat_demand_{t}")

        # ---- 成層蓄熱槽: 層別温度ダイナミクス(移流は風上差分=双線形) ----
        for l in L:
            # 蓄熱流(下向き): 上流は l=0 なら二次送水、それ以外は一つ上の層
            up_in = T_ssup[t] if l == 0 else T_lay[l - 1, t]
            # 放熱流(上向き): 上流は最下層なら需要家戻り、それ以外は一つ下の層
            dn_in = T_SRET if l == nL - 1 else T_lay[l + 1, t]
            advect = CP * m_chg[t] * (up_in - T_lay[l, t]) + CP * m_dis[t] * (dn_in - T_lay[l, t])
            # 層間熱伝導(成層の崩壊。両端は断熱境界)
            cond = 0.0
            if l > 0:
                cond += K_COND * (T_lay[l - 1, t] - T_lay[l, t])
            if l < nL - 1:
                cond += K_COND * (T_lay[l + 1, t] - T_lay[l, t])
            loss = UA_LAYER * (T_lay[l, t] - amb)
            m.addCons(
                C_LAYER * (T_lay[l, t + 1] - T_lay[l, t]) == DT_H * (advect + cond - loss),
                name=f"tank_layer_{l}_{t}")

        # ---- 蓄電池: SOCダイナミクス + サイクル劣化の内生化 ----
        m.addCons(soc[t] <= cap[t], name=f"batt_soc_cap_{t}")
        m.addCons(crate[t] * cap[t] >= p_chg[t] + p_dis[t], name=f"batt_crate_{t}")
        m.addCons(dod[t] * cap[t] >= p_dis[t], name=f"batt_dod_{t}")
        m.addCons(
            deg[t] >= K_DEG * (crate[t] ** CRATE_EXP) * (dod[t] ** DOD_EXP),
            name=f"batt_deg_{t}")
        m.addCons(cap[t + 1] == cap[t] - deg[t] * CAP_NOM, name=f"batt_cap_bal_{t}")
        m.addCons(
            soc[t + 1] == soc[t] + DT_H * (ETA_C * p_chg[t] - p_dis[t] / ETA_D),
            name=f"batt_soc_bal_{t}")

        # ---- 電力収支: 熱源機 + 両ポンプの消費を系統購入と蓄電池放電で賄う ----
        m.addCons(
            p_grid[t] + p_dis[t]
            == quicksum(p_hp[k, t] for k in K) + w_p[t] + w_s[t] + p_chg[t],
            name=f"power_balance_{t}")

    # ---- 初期条件・終端条件 ----
    for l in L:
        # 運用開始時は上層ほど高温な成層状態(上層70℃ → 下層は線形に低下)
        T_init = 70.0 - 18.0 * (l / max(1, nL - 1))
        m.addCons(T_lay[l, 0] == T_init, name=f"tank_init_{l}")
    # 蓄熱槽は計画期間の終わりに初期の蓄熱量まで回復させる(翌日へ引き継ぐ運用)。
    # これがないと最適化は初期蓄熱を単に食い潰すだけの解を選び、「いつ蓄熱するか」という
    # 意思決定そのものが消えてしまう(蓄電池の期末SOC下限と同じ役割)。
    m.addCons(quicksum(T_lay[l, nT] for l in L) >= quicksum(T_lay[l, 0] for l in L),
              name="tank_terminal")
    m.addCons(cap[0] == CAP_NOM, name="batt_cap_init")
    m.addCons(soc[0] == 0.5 * CAP_NOM, name="batt_soc_init")
    m.addCons(soc[nT] >= SOC_TERMINAL_FRAC * cap[nT], name="batt_soc_terminal")

    # ================= 目的関数 =================
    elec_cost = quicksum(float(price_elec[t]) * p_grid[t] * DT_H for t in T)
    boiler_cost = quicksum(BOILER_COST * q_boiler[t] * DT_H for t in T)
    degradation_cost = quicksum(deg[t] * CAP_NOM * REPLACEMENT_COST for t in T)
    m.setObjective(elec_cost + boiler_cost + degradation_cost, "minimize")

    m.data = dict(z_hp=z_hp, p_hp=p_hp, q_hp=q_hp, T_hot=T_hot, T_pret=T_pret,
                  T_ssup=T_ssup, T_cret=T_cret, lmtd=lmtd, q_hx=q_hx,
                  n_p=n_p, n_s=n_s, w_p=w_p, w_s=w_s, T_lay=T_lay,
                  m_chg=m_chg, m_dis=m_dis, q_boiler=q_boiler,
                  soc=soc, cap=cap, p_grid=p_grid,
                  scale=scale, dims=(nK, nT, nL))
    return m


def main() -> None:
    m = build_model("small")
    # small でも最適性の証明までは到達しない(docstring の注意書きを参照)。
    # 手元で試すときに終わらないと困るので、明示的に打ち切って実行可能解を見る。
    m.setParam("limits/time", 120.0)
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")
        nK, nT, nL = m.data["dims"]
        lmtd, w_s, T_lay = m.data["lmtd"], m.data["w_s"], m.data["T_lay"]
        print(f"LMTD range : {min(m.getVal(lmtd[t]) for t in range(nT)):.2f}"
              f" .. {max(m.getVal(lmtd[t]) for t in range(nT)):.2f} K")
        print(f"secondary pump power: {max(m.getVal(w_s[t]) for t in range(nT)):.2f} kW (peak)")
        print("tank stratification (final): "
              + " / ".join(f"{m.getVal(T_lay[l, nT]):.1f}" for l in range(nL)) + " degC")


if __name__ == "__main__":
    main()
