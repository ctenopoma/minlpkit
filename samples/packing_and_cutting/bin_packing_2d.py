"""梱包資材の2次元ビンパッキング問題 (2D Bin Packing Problem)

事業ストーリー
--------------
出荷センターの梱包担当者が、当日出荷する矩形の荷物(部材・製品パッケージなど)を、
できるだけ少ない枚数の定尺パレット(またはコンテナ床面)に詰め込む計画を立てる問題である。
荷物は回転させずにそのままの向きで置く前提とし、パレット上で荷物同士が重ならないように
配置しなければならない。使用するパレット枚数を減らせれば、輸送費(パレット単位の
トラック積載料金)や倉庫の保管スペースを直接的に削減できるため、梱包計画の巧拙が
物流コストに直結する。

各制約の業務的意味:
- **各荷物は必ず1枚のパレットに割当**: 荷物を分割して複数パレットに跨って
  置くことはできない。
- **パレット境界内に収める**: 荷物の右端・上端がパレットの幅・高さを超えてはならない
  (パレットからはみ出た荷物は輸送中に破損・落下するリスクがある)。
- **使用パレットの整合**: 荷物が置かれたパレットは「使用中」として扱われ、
  未使用パレットには何も置けない。
- **非重複制約(4方向のいずれかで分離)**: 同じパレットに載る荷物同士は、
  左右または上下のいずれかの方向で確実に離れていなければならない
  (現実の荷物は互いにめり込めない)。

(元の学術的定式化: Lodi, A., Martello, S., & Vigo, D. (2002). Two-dimensional
packing problems: A survey. European Journal of Operational Research.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("BinPacking2D")

    # パレット(定尺)のサイズと、当日出荷する荷物(幅, 高さ)のリスト
    bin_W = 12
    bin_H = 10
    items = [
        (4, 5), (6, 4), (5, 6), (3, 3), (6, 3),
        (4, 4), (5, 3), (3, 5),
    ]
    n = len(items)
    max_bins = 4

    # 変数
    y = {}  # y[k] = 1 のときパレットkを使用
    x = {}  # x[i, k] = 1 のとき荷物iをパレットkに割当
    pos_x = {}  # 荷物iの左下角のx座標
    pos_y = {}  # 荷物iの左下角のy座標

    for k in range(max_bins):
        y[k] = model.addVar(vtype="B", name=f"use_bin_{k}")
        for i in range(n):
            x[i, k] = model.addVar(vtype="B", name=f"assign_{i}_{k}")

    for i in range(n):
        pos_x[i] = model.addVar(vtype="C", lb=0, name=f"pos_x_{i}")
        pos_y[i] = model.addVar(vtype="C", lb=0, name=f"pos_y_{i}")

    # 制約
    # 各荷物は必ず1枚のパレットに割当
    for i in range(n):
        model.addCons(quicksum(x[i, k] for k in range(max_bins)) == 1, name=f"assign_item_{i}")

    # パレット境界内に収める
    for i in range(n):
        w, h = items[i]
        model.addCons(pos_x[i] + w <= bin_W, name=f"bound_x_{i}")
        model.addCons(pos_y[i] + h <= bin_H, name=f"bound_y_{i}")

    # 使用パレットの整合(未使用パレットには何も置けない)
    for i in range(n):
        for k in range(max_bins):
            model.addCons(x[i, k] <= y[k], name=f"usage_{i}_{k}")

    # 非重複制約(big-Mで4方向いずれかの分離を強制)
    bigM = max(bin_W, bin_H)
    z = {}  # 相対位置を表す指示変数
    for i in range(n):
        for j in range(n):
            if i < j:
                z[i, j, 0] = model.addVar(vtype="B", name=f"z_{i}_{j}_left")
                z[i, j, 1] = model.addVar(vtype="B", name=f"z_{i}_{j}_right")
                z[i, j, 2] = model.addVar(vtype="B", name=f"z_{i}_{j}_below")
                z[i, j, 3] = model.addVar(vtype="B", name=f"z_{i}_{j}_above")

                # 同じパレットに載る場合は重ならないようにする
                same_bin = model.addVar(vtype="B", name=f"same_bin_{i}_{j}")
                for k in range(max_bins):
                    model.addCons(same_bin >= x[i, k] + x[j, k] - 1, name=f"same_bin_lower_{i}_{j}_{k}")

                w_i, h_i = items[i]
                w_j, h_j = items[j]

                model.addCons(pos_x[i] + w_i <= pos_x[j] + bigM * (1 - z[i, j, 0]), name=f"no_ovlap_l_{i}_{j}")
                model.addCons(pos_x[j] + w_j <= pos_x[i] + bigM * (1 - z[i, j, 1]), name=f"no_ovlap_r_{i}_{j}")
                model.addCons(pos_y[i] + h_i <= pos_y[j] + bigM * (1 - z[i, j, 2]), name=f"no_ovlap_b_{i}_{j}")
                model.addCons(pos_y[j] + h_j <= pos_y[i] + bigM * (1 - z[i, j, 3]), name=f"no_ovlap_a_{i}_{j}")

                model.addCons(z[i, j, 0] + z[i, j, 1] + z[i, j, 2] + z[i, j, 3] >= same_bin, name=f"no_ovlap_sum_{i}_{j}")

    if infeasible:
        model.addCons(quicksum(y[k] for k in range(max_bins)) == 0, name="inf_constraint")

    # 目的関数: 使用パレット枚数の最小化
    model.setObjective(quicksum(y[k] for k in range(max_bins)), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
