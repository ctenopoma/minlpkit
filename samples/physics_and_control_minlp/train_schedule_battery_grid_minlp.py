"""列車ダイヤ・車載蓄電池SOC・き電網潮流の同時最適化 (MINLP).

事業ストーリー
--------------
直流電化路線を運行する鉄道事業者の「運行計画部門と電力部門の合同チーム」が、1つの
ラッシュ時間帯について「各列車が各駅を何分に発車するか(ダイヤ)」「駅間をどの走行
パターン(所要時間の短い高速型 / 加減速を抑えた省エネ型)で走るか」「車載蓄電池を
いつ充放電するか」を**同時に**決める意思決定である。

従来これらは分断されている——運行計画はダイヤだけを作り、電力部門は与えられたダイヤに
対して変電所容量を設計する。しかし直流き電では、**ある列車の回生ブレーキ電力は、
同じき電区間で同時に力行している別の列車がいて初めて使える**。誰も受け取らなければ
架線電圧が上昇し、回生失効(ブレーキ絞り込み)となって抵抗器で熱として捨てられる。
つまり「発車時刻を数十秒ずらす」というダイヤ側の判断が、そのまま電力側の損失を左右する。
車載蓄電池はこの時間的ミスマッチを吸収する緩衝材だが、容量とSOC窓に縛られる。

各制約・非線形項の業務的意味:
- **ダイヤ決定(離散、時刻窓 × 走行パターン)**: 各列車・各駅について、基準ダイヤの前後
  数スロットの**発車時刻**と、駅間の**走行パターン**(所要時間の短い高速モードほど
  加速度と最高速度が高く消費エネルギーが大きい)を選ぶ二重の離散決定。
  `x[i,s,mode,tau]` が「列車 i が駅 s を時刻 tau に mode で発車」を表す。
- **走行抵抗と牽引電力(データとして厳密に事前計算)**: 各 (駅間, 走行パターン) について
  台形速度曲線を解き、Davis式の走行抵抗 `A + B*v + C*v²` と慣性力から
  スロット別の平均機械動力と平均位置を事前計算する。所要時間から巡航速度を逆算する
  二次方程式を解いているため、「速く走るほど二乗以上に電力を食う」という実際の関係が
  データに埋め込まれている(モデル内では発車時刻でシフトするだけなので線形)。
- **き電網の電流注入モデル(固定ノード上の線形回路)**: 架線を等間隔の固定ノード列に
  離散化し、隣接ノード間を一定コンダクタンスで結ぶ。列車は連続的な位置にいるので、
  その電流を**最寄り2ノードへ線形補間して注入**する(有限要素的な電流注入)。
  補間重みは (駅間, 走行パターン, 経過スロット) ごとに事前計算できるため、
  ノードへの注入は `x[...]` の線形結合 × 列車電流という形になる。
  これにより回路そのもの(KCL・オーム則)は線形に保たれ、非凸性は電力 = 電圧 × 電流
  という物理の本質だけに限定される。
- **ダイヤと潮流を結ぶ双線形項(本モデルの核)**: 列車のパンタグラフ電圧は
  `v_pan[i,t] == Σ_n w[i,n,t] * v_node[n,t]` であり、重み `w` はダイヤ変数の線形結合、
  `v_node` は潮流変数。**決定変数同士の積**であり、ここがダイヤ側と電力側を数式レベルで
  不可分にする。ノードへの電流注入 `w[i,n,t] * i_pan[i,t]` も同様。
- **変電所とダイオード整流(回生失効の発生源)**: 直流変電所はシリコン整流器を持つため
  **電流を送り出せても受け取れない**(`i_sub >= 0`)。無負荷電圧から内部抵抗分だけ
  電圧降下する。列車が回生してもき電区間内に受け手がいなければ電流の行き場がなく、
  パンタグラフ電圧が上限 `V_MAX` に張り付いて回生電力を送り出せない。
- **回生失効の明示的モデル化**: 車上の電力収支に「抵抗器で捨てる電力 `p_waste >= 0`」を
  置き、回生電力の行き先を「架線へ送出 / 蓄電池へ充電 / 抵抗器で廃棄」の3択にする。
  電圧上限制約が架線への送出を塞いだとき、蓄電池が空いていなければ廃棄に回る——
  これが回生失効そのものであり、目的関数で直接ペナルティを受ける。
- **車載蓄電池のSOCと劣化**: SOCダイナミクスは充放電効率を伴い、SOC窓
  `[SOC_MIN, SOC_MAX]` に拘束される(リチウムイオンは満充電/深放電付近での使用を避ける)。
  劣化は `deg >= K_DEG * crate^1.5` として充放電速度の非線形なストレスを内生化する。
- **運行上の制約**: 最低停車時分、続行列車との駅発車間隔(運転時隔)、および基準ダイヤ
  からの逸脱ペナルティ(旅客への影響)。エネルギーだけを最適化するとダイヤが崩壊する
  ため、この逸脱ペナルティが現実的な解を選ばせる。なお終着駅への到着期限は、計画対象
  スロット数 `nT` を超える発車を選択肢から除外することで暗黙に課している。

なぜダイヤ・蓄電池・き電網の三者結合が業務要件として自然に入るか:
回生電力の授受には「同じき電区間・同じ瞬間」という厳しい時空間の同時性が要る。
これを満たすかどうかを決めるのはダイヤ(いつ発車するか)であり、満たせなかったときに
救えるのは蓄電池(いつ充放電するか)であり、そもそも授受が成立するかを判定するのは
き電回路(電圧が上限に達しないか)である。三者のどれか一つでも外部から与えられた
定数として扱うと、この同時性の設計余地そのものが消えてしまう。

scale ノブ(硬さの源泉: 物理結合(P=V·I の非凸、ダイヤ変数×潮流変数の双線形) +
統合結合(ダイヤ×蓄電池×き電網) + 離散(発車時刻窓 × 走行パターンの二重選択) +
時間結合(SOCダイナミクス)):
    small   : 列車2 × 駅3 × 16スロット × ノード5(変電所2)   (テスト・ハンズオン用)
    default : 列車3 × 駅4 × 28スロット × ノード7(変電所2)   (診断の題材。gap残存を是とする)
    large   : 列車4 × 駅5 × 40スロット × ノード9(変電所3)
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_train=2, n_station=3, n_slot=16, n_node=5, n_sub=2, window=3),
    "default": dict(n_train=3, n_station=4, n_slot=28, n_node=7, n_sub=2, window=4),
    "large":   dict(n_train=4, n_station=5, n_slot=40, n_node=9, n_sub=3, window=5),
}

DT_SLOT = 30.0               # 1スロットの長さ [s]
LINE_LENGTH = 6000.0         # 路線全長 [m]

# --- 車両パラメータ ---
MASS = 160000.0              # 編成質量 [kg](慣性質量を含む)
DAVIS_A = 2200.0             # 走行抵抗 定数項 [N]
DAVIS_B = 55.0               # 走行抵抗 速度比例項 [N/(m/s)]
DAVIS_C = 6.5                # 走行抵抗 速度二乗項 [N/(m/s)^2]
EFF_TR = 0.88                # 力行時の電気→機械 効率
EFF_REG = 0.85               # 回生時の機械→電気 効率

# 走行パターン(mode): (所要スロット数, 最大加速度[m/s^2], 最大減速度[m/s^2])
MODES = {
    "fast": (5, 0.90, 0.90),
    "eco":  (7, 0.60, 0.70),
}

# --- き電回路 ---
V_NL = 1600.0                # 変電所の無負荷送り出し電圧 [V]
R_SUB = 0.055                # 変電所の内部抵抗 [Ω]
R_LINE = 0.035               # 架線+レールの単位長抵抗 [Ω/km]
V_PAN_MIN = 1000.0           # パンタグラフ電圧の下限 [V](これを割ると走行不能)
V_PAN_MAX = 1750.0           # パンタグラフ電圧の上限 [V](これに張り付くと回生失効)
I_PAN_MAX = 3000.0           # パンタグラフ電流の上限 [A]
I_SUB_MAX = 4000.0           # 変電所の最大送り出し電流 [A]

# --- 車載蓄電池 ---
BATT_CAP = 240.0             # 容量 [kWh]
SOC_MIN_FRAC, SOC_MAX_FRAC = 0.25, 0.90   # SOC窓(容量比)
SOC_INIT_FRAC = 0.60
SOC_TERM_FRAC = 0.50         # 期末SOC下限(次の運用に引き継ぐ)
P_BATT_MAX = 400.0           # 最大充放電電力 [kW]
ETA_C, ETA_D = 0.96, 0.96    # 充放電効率
K_DEG = 3.0e-4               # 劣化速度係数
CRATE_EXP = 1.5
REPLACEMENT_COST = 320.0     # 容量1kWhあたりの更新投資費 [$/kWh]

# --- 運行制約 ---
MIN_DWELL_SLOT = 1           # 最低停車スロット数
HEADWAY_SLOT = 2             # 続行列車との最低発車間隔(運転時隔)スロット数

# --- コスト ---
PRICE_ENERGY = 0.14          # 変電所からの購入電力単価 [$/kWh]
PRICE_PEAK = 0.90            # ピーク電力課金 [$/kW](最大変電所出力に対する契約課金)
PENALTY_WASTE = 0.30         # 回生失効(抵抗器での廃棄)のペナルティ [$/kWh]
PENALTY_SCHEDULE = 2.5       # 基準ダイヤからの逸脱ペナルティ [$/スロット・列車]


def _leg_profile(distance: float, run_slots: int, accel: float, decel: float):
    """台形速度曲線を解き、スロット別の (平均位置比, 平均機械動力[kW]) を返す。

    所要時間 `run_slots*DT_SLOT` と走行距離から巡航速度を二次方程式で逆算し、
    1秒刻みで積分してスロット平均に集約する。機械動力は
    `(慣性力 + Davis走行抵抗) * 速度` で、減速中は負(回生可能)になる。
    """
    T_run = run_slots * DT_SLOT
    # D = v*T - v^2/(2a) - v^2/(2b)  →  k*v^2 - T*v + D = 0
    k = 0.5 / accel + 0.5 / decel
    disc = T_run * T_run - 4.0 * k * distance
    if disc < 0.0:
        # 与えられた所要時間では走りきれない → 巡航速度を最大化する解に丸める
        v_cruise = T_run / (2.0 * k)
    else:
        v_cruise = (T_run - np.sqrt(disc)) / (2.0 * k)

    t_acc = v_cruise / accel
    t_dec = v_cruise / decel
    t_cru = max(0.0, T_run - t_acc - t_dec)

    n_fine = int(round(T_run))
    pos = np.zeros(n_fine)
    pmech = np.zeros(n_fine)
    x, v = 0.0, 0.0
    for i in range(n_fine):
        tau = i + 0.5
        if tau < t_acc:
            a = accel
        elif tau < t_acc + t_cru:
            a = 0.0
        else:
            a = -decel
        v = max(0.0, v + a * 1.0)
        x += v * 1.0
        resist = DAVIS_A + DAVIS_B * v + DAVIS_C * v * v
        force = MASS * a + resist
        # 減速中に走行抵抗が制動を上回る場合は回生できない(動力は0でクリップしない:
        # force*v が負なら回生、正なら力行。惰行に近い領域では自然に小さくなる)
        pos[i] = x
        pmech[i] = force * v / 1000.0     # [kW]

    # 実距離との整合(数値積分誤差の補正)
    if pos[-1] > 1e-6:
        pos = pos * (distance / pos[-1])

    # スロット平均へ集約
    slot_pos = np.zeros(run_slots)
    slot_pow = np.zeros(run_slots)
    for s in range(run_slots):
        lo, hi = int(s * DT_SLOT), min(n_fine, int((s + 1) * DT_SLOT))
        slot_pos[s] = pos[lo:hi].mean()
        slot_pow[s] = pmech[lo:hi].mean()
    return slot_pos, slot_pow


def _data(scale: str):
    cfg = SCALES[scale]
    nI, nS, nT = cfg["n_train"], cfg["n_station"], cfg["n_slot"]
    nN, nA, W = cfg["n_node"], cfg["n_sub"], cfg["window"]
    rng = np.random.default_rng(20260728 + nI * 31 + nS * 13 + nT * 5)

    # 駅位置(等間隔ではなく、都心寄りを密に)
    frac = np.linspace(0.0, 1.0, nS) ** 1.25
    sta_pos = LINE_LENGTH * frac

    # き電ノード(等間隔)と変電所の設置ノード
    node_pos = np.linspace(0.0, LINE_LENGTH, nN)
    sub_nodes = [int(round(a * (nN - 1) / max(1, nA - 1))) for a in range(nA)]

    # (駅間, 走行パターン) ごとの位置・機械動力プロファイル
    mode_names = list(MODES.keys())
    profile: dict[tuple[int, str], tuple[np.ndarray, np.ndarray]] = {}
    for s in range(nS - 1):
        dist = float(sta_pos[s + 1] - sta_pos[s])
        for mname in mode_names:
            run_slots, acc, dec = MODES[mname]
            rel_pos, pw = _leg_profile(dist, run_slots, acc, dec)
            profile[s, mname] = (float(sta_pos[s]) + rel_pos, pw)

    # 基準ダイヤ(列車 i が駅 s を発車する基準スロット)。運転時隔ぶんずつずらす
    nominal = np.zeros((nI, nS - 1), dtype=int)
    for i in range(nI):
        t_cur = i * HEADWAY_SLOT
        for s in range(nS - 1):
            nominal[i, s] = t_cur
            t_cur += MODES["eco"][0] + MIN_DWELL_SLOT
    # 発車時刻窓(基準の前後。負・範囲外は後で除外)
    offsets = list(range(-(W // 2), W - (W // 2)))

    # 列車ごとの乗車率(質量には反映済みとし、ここでは補機負荷[kW]として効かせる)
    aux_load = rng.uniform(35.0, 65.0, nI)

    return dict(nI=nI, nS=nS, nT=nT, nN=nN, nA=nA,
                sta_pos=sta_pos, node_pos=node_pos, sub_nodes=sub_nodes,
                mode_names=mode_names, profile=profile,
                nominal=nominal, offsets=offsets, aux_load=aux_load)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nI, nS, nT, nN = d["nI"], d["nS"], d["nT"], d["nN"]
    node_pos, sub_nodes = d["node_pos"], d["sub_nodes"]
    mode_names, profile = d["mode_names"], d["profile"]
    nominal, offsets, aux_load = d["nominal"], d["offsets"], d["aux_load"]

    m = Model("Train_Schedule_Battery_Grid")
    I, S, T, N = range(nI), range(nS - 1), range(nT), range(nN)
    A = range(len(sub_nodes))

    dx_km = float(node_pos[1] - node_pos[0]) / 1000.0
    G_LINE = 1.0 / (R_LINE * dx_km)      # 隣接ノード間コンダクタンス [S]

    # ================= ダイヤ変数 =================
    # x[i,s,mode,tau] = 1 : 列車 i が駅 s を スロット tau に mode で発車
    x: dict[tuple, object] = {}
    dep_choices: dict[tuple[int, int], list[tuple[str, int]]] = {}
    for i in I:
        for s in S:
            choices = []
            for mname in mode_names:
                run_slots = MODES[mname][0]
                for off in offsets:
                    tau = int(nominal[i, s]) + off
                    if tau < 0 or tau + run_slots > nT:
                        continue
                    choices.append((mname, tau))
                    x[i, s, mname, tau] = m.addVar(
                        vtype="B", name=f"x_{i}_{s}_{mname}_{tau}")
            if not choices:
                raise ValueError(
                    f"列車{i} 駅{s} の発車時刻窓がスロット数に収まらない(scale設定を見直す)")
            dep_choices[i, s] = choices

    for i in I:
        for s in S:
            m.addCons(quicksum(x[i, s, mn, tau] for mn, tau in dep_choices[i, s]) == 1,
                      name=f"depart_once_{i}_{s}")

    # 発車スロットの数値表現(線形)
    def dep_time(i: int, s: int):
        return quicksum(float(tau) * x[i, s, mn, tau] for mn, tau in dep_choices[i, s])

    def arr_time(i: int, s: int):
        return quicksum(float(tau + MODES[mn][0]) * x[i, s, mn, tau]
                        for mn, tau in dep_choices[i, s])

    # 最低停車時分(前の駅間の到着 + 停車 <= 次の駅間の発車)
    for i in I:
        for s in range(nS - 2):
            m.addCons(dep_time(i, s + 1) >= arr_time(i, s) + MIN_DWELL_SLOT,
                      name=f"dwell_{i}_{s}")

    # 運転時隔(続行列車は各駅で HEADWAY_SLOT 以上あける)
    for i in range(nI - 1):
        for s in S:
            m.addCons(dep_time(i + 1, s) >= dep_time(i, s) + HEADWAY_SLOT,
                      name=f"headway_{i}_{s}")

    # ================= 事前計算: ノード注入重みと機械動力 =================
    # weight[i, n, t] : 列車 i が スロット t にノード n へ寄与する割合(ダイヤ変数の線形結合)
    # pmech_pos/neg[i, t] : 力行/回生の機械動力 [kW](同じくダイヤ変数の線形結合)
    weight: dict[tuple[int, int, int], object] = {}
    pmech_pos: dict[tuple[int, int], object] = {}
    pmech_neg: dict[tuple[int, int], object] = {}
    onboard: dict[tuple[int, int], object] = {}   # スロット t に列車 i が走行中か(0/1の線形結合)

    for i in I:
        for t in T:
            w_terms: dict[int, list] = {n: [] for n in N}
            pos_terms, neg_terms, on_terms = [], [], []
            for s in S:
                for mn, tau in dep_choices[i, s]:
                    run_slots = MODES[mn][0]
                    k = t - tau
                    if k < 0 or k >= run_slots:
                        continue
                    prof_pos, prof_pow = profile[s, mn]
                    p_here = float(prof_pos[k])
                    pw = float(prof_pow[k])
                    # 最寄り2ノードへの線形補間重み
                    idx = min(nN - 2, max(0, int(p_here / (node_pos[1] - node_pos[0]))))
                    frac = (p_here - node_pos[idx]) / (node_pos[idx + 1] - node_pos[idx])
                    frac = min(1.0, max(0.0, frac))
                    w_terms[idx].append((1.0 - frac) * x[i, s, mn, tau])
                    w_terms[idx + 1].append(frac * x[i, s, mn, tau])
                    on_terms.append(x[i, s, mn, tau])
                    if pw >= 0.0:
                        pos_terms.append(pw * x[i, s, mn, tau])
                    else:
                        neg_terms.append((-pw) * x[i, s, mn, tau])
            for n in N:
                weight[i, n, t] = quicksum(w_terms[n]) if w_terms[n] else 0.0
            pmech_pos[i, t] = quicksum(pos_terms) if pos_terms else 0.0
            pmech_neg[i, t] = quicksum(neg_terms) if neg_terms else 0.0
            onboard[i, t] = quicksum(on_terms) if on_terms else 0.0

    # ================= 電気変数 =================
    v_node = {(n, t): m.addVar(vtype="C", lb=V_PAN_MIN - 200.0, ub=V_NL + 100.0,
                               name=f"v_node_{n}_{t}") for n in N for t in T}
    i_sub = {(a, t): m.addVar(vtype="C", lb=0.0, ub=I_SUB_MAX, name=f"i_sub_{a}_{t}")
             for a in A for t in T}
    p_sub = {(a, t): m.addVar(vtype="C", lb=0.0, name=f"p_sub_{a}_{t}")
             for a in A for t in T}
    p_peak = m.addVar(vtype="C", lb=0.0, name="p_peak")

    i_pan, v_pan, p_pan = {}, {}, {}
    for i in I:
        for t in T:
            # 力行で正、回生で負
            i_pan[i, t] = m.addVar(vtype="C", lb=-I_PAN_MAX, ub=I_PAN_MAX, name=f"i_pan_{i}_{t}")
            v_pan[i, t] = m.addVar(vtype="C", lb=0.0, ub=V_PAN_MAX, name=f"v_pan_{i}_{t}")
            p_pan[i, t] = m.addVar(vtype="C", lb=-5000.0, ub=5000.0, name=f"p_pan_{i}_{t}")

    # ================= 蓄電池変数 =================
    soc = {(i, t): m.addVar(vtype="C", lb=SOC_MIN_FRAC * BATT_CAP, ub=SOC_MAX_FRAC * BATT_CAP,
                            name=f"soc_{i}_{t}") for i in I for t in range(nT + 1)}
    b_chg, b_dis, crate, deg, p_waste = ({} for _ in range(5))
    for i in I:
        for t in T:
            b_chg[i, t] = m.addVar(vtype="C", lb=0.0, ub=P_BATT_MAX, name=f"b_chg_{i}_{t}")
            b_dis[i, t] = m.addVar(vtype="C", lb=0.0, ub=P_BATT_MAX, name=f"b_dis_{i}_{t}")
            crate[i, t] = m.addVar(vtype="C", lb=0.0, ub=3.0, name=f"crate_{i}_{t}")
            deg[i, t] = m.addVar(vtype="C", lb=0.0, ub=0.02, name=f"deg_{i}_{t}")
            p_waste[i, t] = m.addVar(vtype="C", lb=0.0, ub=5000.0, name=f"p_waste_{i}_{t}")

    # ================= 制約 =================
    dt_h = DT_SLOT / 3600.0

    for t in T:
        # ---- 変電所: 無負荷電圧から内部抵抗降下。ダイオード整流のため i_sub >= 0 ----
        for a in A:
            node = sub_nodes[a]
            m.addCons(v_node[node, t] == V_NL - R_SUB * i_sub[a, t], name=f"sub_v_{a}_{t}")
            m.addCons(p_sub[a, t] == v_node[node, t] * i_sub[a, t] / 1000.0,
                      name=f"sub_p_{a}_{t}")
            m.addCons(p_peak >= p_sub[a, t], name=f"peak_{a}_{t}")

        # ---- KCL: 各ノードで「変電所送出 = 隣接ノードへの流出 + 列車の吸い上げ」 ----
        for n in N:
            inflow = quicksum(i_sub[a, t] for a in A if sub_nodes[a] == n)
            neigh = 0.0
            if n > 0:
                neigh += G_LINE * (v_node[n, t] - v_node[n - 1, t])
            if n < nN - 1:
                neigh += G_LINE * (v_node[n, t] - v_node[n + 1, t])
            # 列車電流の注入(重みはダイヤ変数の線形結合 → 双線形)
            train_draw = quicksum(weight[i, n, t] * i_pan[i, t] for i in I)
            m.addCons(inflow == neigh + train_draw, name=f"kcl_{n}_{t}")

        for i in I:
            # ---- パンタグラフ電圧 = ノード電圧の補間(ダイヤ変数 × 潮流変数の双線形) ----
            m.addCons(
                v_pan[i, t] == quicksum(weight[i, n, t] * v_node[n, t] for n in N),
                name=f"pan_v_{i}_{t}")
            # 走行中のみ電圧下限を課す(在線していないスロットは回路から切り離す)
            m.addCons(v_pan[i, t] >= V_PAN_MIN * onboard[i, t], name=f"pan_vmin_{i}_{t}")
            m.addCons(v_pan[i, t] <= V_PAN_MAX * onboard[i, t], name=f"pan_vmax_{i}_{t}")
            m.addCons(i_pan[i, t] <= I_PAN_MAX * onboard[i, t], name=f"pan_imax_{i}_{t}")
            m.addCons(i_pan[i, t] >= -I_PAN_MAX * onboard[i, t], name=f"pan_imin_{i}_{t}")

            # ---- 電力 = 電圧 × 電流(非凸) ----
            m.addCons(p_pan[i, t] == v_pan[i, t] * i_pan[i, t] / 1000.0, name=f"pan_p_{i}_{t}")

            # ---- 車上の電力収支 ----
            # 力行needs = 機械動力/効率 + 補機、回生avail = 機械動力 * 効率
            need = pmech_pos[i, t] / EFF_TR + float(aux_load[i]) * onboard[i, t]
            avail = EFF_REG * pmech_neg[i, t]
            m.addCons(
                p_pan[i, t] + b_dis[i, t] + avail
                == need + b_chg[i, t] + p_waste[i, t],
                name=f"train_power_{i}_{t}")

            # ---- 蓄電池 ----
            m.addCons(crate[i, t] * BATT_CAP >= b_chg[i, t] + b_dis[i, t],
                      name=f"batt_crate_{i}_{t}")
            m.addCons(deg[i, t] >= K_DEG * (crate[i, t] ** CRATE_EXP),
                      name=f"batt_deg_{i}_{t}")
            m.addCons(
                soc[i, t + 1] == soc[i, t] + dt_h * (ETA_C * b_chg[i, t] - b_dis[i, t] / ETA_D),
                name=f"batt_soc_{i}_{t}")

    for i in I:
        m.addCons(soc[i, 0] == SOC_INIT_FRAC * BATT_CAP, name=f"soc_init_{i}")
        m.addCons(soc[i, nT] >= SOC_TERM_FRAC * BATT_CAP, name=f"soc_term_{i}")

    # ================= 目的関数 =================
    energy_cost = quicksum(PRICE_ENERGY * p_sub[a, t] * dt_h for a in A for t in T)
    peak_cost = PRICE_PEAK * p_peak
    waste_cost = quicksum(PENALTY_WASTE * p_waste[i, t] * dt_h for i in I for t in T)
    deg_cost = quicksum(deg[i, t] * BATT_CAP * REPLACEMENT_COST for i in I for t in T)
    # 基準ダイヤからの逸脱(発車スロットの前後ずれ。絶対値を上下から挟む補助変数で表現)
    dev = {}
    for i in I:
        for s in S:
            dev[i, s] = m.addVar(vtype="C", lb=0.0, name=f"dev_{i}_{s}")
            m.addCons(dev[i, s] >= dep_time(i, s) - float(nominal[i, s]), name=f"dev_p_{i}_{s}")
            m.addCons(dev[i, s] >= float(nominal[i, s]) - dep_time(i, s), name=f"dev_n_{i}_{s}")
    sched_cost = quicksum(PENALTY_SCHEDULE * dev[i, s] for i in I for s in S)

    m.setObjective(energy_cost + peak_cost + waste_cost + deg_cost + sched_cost, "minimize")

    m.data = dict(x=x, dep_choices=dep_choices, v_node=v_node, v_pan=v_pan,
                  i_pan=i_pan, p_pan=p_pan, p_sub=p_sub, p_peak=p_peak,
                  soc=soc, b_chg=b_chg, b_dis=b_dis, p_waste=p_waste, dev=dev,
                  nominal=nominal, scale=scale, dims=(nI, nS, nT, nN))
    return m


def main() -> None:
    m = build_model("small")
    # P=V·I とダイヤ×潮流の双線形を含むため、打ち切って実行可能解を見る
    # (実測では small は 120 秒程度で gap 1% 未満まで到達する)。
    m.setParam("limits/time", 120.0)
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")
        nI, nS, nT, nN = m.data["dims"]
        dep_choices, x = m.data["dep_choices"], m.data["x"]
        nominal = m.data["nominal"]
        for i in range(nI):
            plan = []
            for s in range(nS - 1):
                for mn, tau in dep_choices[i, s]:
                    if m.getVal(x[i, s, mn, tau]) > 0.5:
                        plan.append(f"駅{s}:t={tau}({mn},基準{nominal[i, s]})")
            print(f"  列車{i}: " + " ".join(plan))
        waste = sum(m.getVal(m.data["p_waste"][i, t]) for i in range(nI) for t in range(nT))
        print(f"  回生失効(廃棄)合計: {waste:.1f} kW·slot")
        print(f"  変電所ピーク: {m.getVal(m.data['p_peak']):.1f} kW")


if __name__ == "__main__":
    main()
