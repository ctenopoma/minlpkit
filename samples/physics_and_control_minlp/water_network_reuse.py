"""工場内 用水・再利用ネットワーク (Industrial Water Reuse Network Synthesis).

事業ストーリー
--------------
化学/製紙/半導体などの工場の「ユーティリティ設計チーム」が、複数の水使用プロセス
(洗浄・冷却・反応など)の間に**再利用配管**をどう敷設し、各プロセスへ淡水・再利用水・
再生水をどう配分するかを決め、**淡水購入費と排水処理費と設備費を最小化**する意思決定である。
水使用プロセスネットワーク合成(water-using network synthesis)として知られる古典的な
強非凸 MINLP。

各制約の業務的意味:
- **汚染物質濃度の質量収支(濃度×流量=双線形)**: 各プロセスは一定量の汚染物質(COD・塩分等)を
  水に加える。プロセス入口の濃度は「流入する各水流の 流量×濃度 の和 ÷ 総流量」で決まり、
  出口濃度は入口濃度に負荷を足したもの。混合点の **流量×濃度** が本質的な双線形項。
- **再利用配管の on/off と流量**: あるプロセスの排水を別プロセスの給水へ再利用するには配管を
  敷設する必要があり、敷設は固定費を伴う離散決定(バイナリ)。配管が無ければ流量は0。
- **入口/出口の濃度上限**: プロセスは汚れすぎた水を受け入れられない(入口濃度上限)、
  排水規制で出口濃度に上限がある。これが再利用の可否を物理的に縛る。
- **再生処理の規模の経済(凹費用)**: 排水を再生処理装置で浄化して再利用できる。処理費は
  処理量に対して**凹(economy of scale)** — 大量処理ほど単位費用が下がる。これを区分線形近似で
  なく素の非凸べき乗 `TT^0.7` として持つ(凹費用の最小化は非凸=緩和が緩む)。
- **淡水・排水コスト**: 淡水は購入費、排水は処理費がかかるため、再利用・再生で淡水と排水を
  減らす誘因が生まれる。

なぜ非凸が業務要件として自然に入るか:
「汚れた水を混ぜて薄めて再利用する」という水回りの運用そのものが 流量×濃度 の双線形を生み、
再生処理の規模の経済が凹費用(非凸)を生む。どちらも近似ではなく設計上の物理・経済そのもの。
SCIP は空間分枝限定法で厳密求解するが、双線形の混合と凹費用で緩和が緩く、既定scaleでは
gap が残る(診断で weak_relaxation / wide_term_range が題材になる)。
淡水100%・再利用なしの解が常に実行可能なので、求解は常に可行解を持つ。

scale ノブ(硬さの源泉: 現実規模 + 物理結合(濃度×流量)+ 統合意思決定(配管敷設+運用)):
    small   : プロセス4      (テスト・ハンズオン用。数分で最適)
    default : プロセス9      (診断の題材。30秒でgap残存)
    large   : プロセス13
"""
from __future__ import annotations

import numpy as np
from pyscipopt import Model, quicksum

SCALES = {
    "small":   dict(n_proc=3),
    "default": dict(n_proc=9),
    "large":   dict(n_proc=13),
}

C_REGEN = 20.0      # 再生処理装置の出口濃度[ppm](浄化後)
C_MAX = 1000.0      # 濃度の物理上限[ppm]


def _data(scale: str):
    nP = SCALES[scale]["n_proc"]
    rng = np.random.default_rng(31415 + nP * 97)

    load = np.round(rng.uniform(2.0, 12.0, nP), 2)        # 汚染負荷[kg/h]
    fmin = np.round(rng.uniform(20, 60, nP), 1)           # 必要通水量[t/h]
    fmax = np.round(fmin + rng.uniform(40, 90, nP), 1)    # 通水量上限
    # 入口濃度上限をタイトに(20〜120ppm): 再利用水の希釈=双線形混合を強く働かせる
    cin_max = np.round(rng.uniform(20, 120, nP), 1)       # 入口濃度上限[ppm]
    cout_max = np.round(cin_max + rng.uniform(150, 500, nP), 1)  # 出口濃度上限
    cout_max = np.minimum(cout_max, C_MAX)
    # 再利用配管の敷設固定費(距離・口径のばらつき)
    pipe_fix = np.round(rng.uniform(30, 120, (nP, nP)), 1)

    # 淡水・排水を高コストにして再利用/再生を必須化(=双線形混合と凹費用が効く)
    fresh_cost = 25.0    # 淡水単価[$/t]
    disch_cost = 15.0    # 排水処理単価[$/t]
    regen_fix = 250.0    # 再生装置の固定費
    regen_k = 45.0       # 再生処理の凹費用係数(k * TT^0.7)

    return dict(nP=nP, load=load, fmin=fmin, fmax=fmax, cin_max=cin_max,
                cout_max=cout_max, pipe_fix=pipe_fix, fresh_cost=fresh_cost,
                disch_cost=disch_cost, regen_fix=regen_fix, regen_k=regen_k)


def build_model(scale: str = "default") -> Model:
    d = _data(scale)
    nP = d["nP"]
    load, fmin, fmax = d["load"], d["fmin"], d["fmax"]
    cin_max, cout_max = d["cin_max"], d["cout_max"]
    pipe_fix = d["pipe_fix"]
    fresh_cost, disch_cost = d["fresh_cost"], d["disch_cost"]
    regen_fix, regen_k = d["regen_fix"], d["regen_k"]

    m = Model("Water_Reuse_Network")
    P = range(nP)

    # --- 変数 ---
    fw = {p: m.addVar(vtype="C", lb=0.0, ub=float(fmax[p]), name=f"fw_{p}") for p in P}
    F = {p: m.addVar(vtype="C", lb=float(fmin[p]), ub=float(fmax[p]), name=f"F_{p}")
         for p in P}
    cin = {p: m.addVar(vtype="C", lb=0.0, ub=float(cin_max[p]), name=f"cin_{p}")
           for p in P}
    cout = {p: m.addVar(vtype="C", lb=0.0, ub=float(cout_max[p]), name=f"cout_{p}")
            for p in P}
    # 再利用流量 r[q,p] = プロセスq出口 → プロセスp入口(q!=p)
    r = {(q, p): m.addVar(vtype="C", lb=0.0, ub=float(fmax[p]), name=f"r_{q}_{p}")
         for q in P for p in P if q != p}
    y = {(q, p): m.addVar(vtype="B", name=f"y_{q}_{p}")
         for q in P for p in P if q != p}
    treat = {p: m.addVar(vtype="C", lb=0.0, ub=float(fmax[p]), name=f"treat_{p}")
             for p in P}   # p出口から再生処理へ送る量
    rw = {p: m.addVar(vtype="C", lb=0.0, ub=float(fmax[p]), name=f"rw_{p}")
          for p in P}      # p入口へ入る再生水
    disch = {p: m.addVar(vtype="C", lb=0.0, ub=float(fmax[p]), name=f"disch_{p}")
             for p in P}
    TT = m.addVar(vtype="C", lb=0.0, ub=float(fmax.sum()), name="TT")  # 総再生処理量
    zt = m.addVar(vtype="B", name="zt")                                # 再生装置設置
    # 凹費用 k*TT^0.7 のエピグラフ変数(目的は線形に保ち、非凸べき乗は制約へ)
    rc = m.addVar(vtype="C", lb=0.0, name="regen_var_cost")

    # --- 制約 ---
    for p in P:
        # 入口流量収支: 淡水 + 再利用 + 再生水
        m.addCons(F[p] == fw[p] + quicksum(r[q, p] for q in P if q != p) + rw[p],
                  name=f"inlet_flow_{p}")
        # 出口流量収支(通水は保存): 再利用払出 + 再生処理へ + 排水
        m.addCons(F[p] == quicksum(r[p, pp] for pp in P if pp != p)
                  + treat[p] + disch[p], name=f"outlet_flow_{p}")
        # ユニット内 汚染物質収支(双線形): F*cout = F*cin + load
        m.addCons(F[p] * cout[p] == F[p] * cin[p] + float(load[p]),
                  name=f"unit_mass_{p}")
        # 入口 汚染物質収支(双線形): F*cin = Σ 再利用流量×出口濃度 + 再生水×再生濃度
        m.addCons(
            F[p] * cin[p] == quicksum(r[q, p] * cout[q] for q in P if q != p)
            + rw[p] * C_REGEN,
            name=f"inlet_mass_{p}")

    # 再利用配管の on/off(敷設しなければ流量0)
    for (q, p), rv in r.items():
        m.addCons(rv <= float(fmax[p]) * y[q, p], name=f"pipe_{q}_{p}")

    # 再生処理の水収支(処理へ送った量 = 再生水として戻る量)
    m.addCons(TT == quicksum(treat[p] for p in P), name="regen_flow")
    m.addCons(quicksum(rw[p] for p in P) == TT, name="regen_return")
    m.addCons(TT <= float(fmax.sum()) * zt, name="regen_onoff")
    # 凹費用(規模の経済): rc >= k*TT^0.7。最小化なので rc は下界=k*TT^0.7 に張り付く。
    # 区分線形近似でなく素の非凸べき乗として持つ(緩和が緩む=診断の題材)
    m.addCons(rc >= regen_k * (TT ** 0.7), name="regen_cost_def")

    # --- 目的関数: 淡水費 + 排水費 + 配管固定費 + 再生費(固定 + 凹 economy of scale) ---
    fresh = fresh_cost * quicksum(fw[p] for p in P)
    discharge = disch_cost * quicksum(disch[p] for p in P)
    piping = quicksum(float(pipe_fix[q, p]) * y[q, p]
                      for q in P for p in P if q != p)
    m.setObjective(fresh + discharge + piping + regen_fix * zt + rc, "minimize")

    m.data = {"fw": fw, "F": F, "cin": cin, "cout": cout, "r": r, "y": y,
              "treat": treat, "rw": rw, "disch": disch, "TT": TT, "zt": zt,
              "rc": rc, "scale": scale, "dims": (nP,)}
    return m


def main() -> None:
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print(f"total cost: {m.getObjVal():.2f}")


if __name__ == "__main__":
    main()
