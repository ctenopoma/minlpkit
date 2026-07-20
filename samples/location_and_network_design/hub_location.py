"""ハブ&スポーク型物流ネットワークのハブ配置問題 (Hub Location Problem)

事業ストーリー
--------------
広域宅配便事業者のネットワーク設計担当者が、各拠点間で発生する荷物量(フロー)を
踏まえて、どの拠点をハブ(集約・仕分け拠点)として開設するか、そして各スポーク拠点を
どのハブに割り当てるかを同時に決める問題である。全拠点間を直接輸送すると輸送網が
組合せ的に膨れ上がり非効率なので、荷物はいったんハブに集約してから別のハブを経由し、
最後に宛先のスポーク拠点へ配送する「ハブ&スポーク」方式を取る。ハブ間輸送は大口輸送
(トラック幹線便・航空便)によりコストが割り引かれる一方、拠点をハブにするには
仕分け設備・要員の投資が必要になるため開設できるハブ数には上限がある。

各制約の業務的意味:
- **開設ハブ数の上限**: 仕分け拠点の設備投資予算・要員体制から同時に運用できる
  ハブ数は限られる(p-ハブメディアン問題の p)。
- **スポーク拠点は必ず1つのハブに割当**: 各拠点の荷物集約先を一意に決めないと
  配送ルートが定まらない。
- **開設していないハブへの割当禁止**: 仕分け設備のない拠点をハブとして使うことは
  物理的にできない。
- **ハブ間割引率**: 大口幹線輸送(トラックの積載効率向上・航空便の規模の経済)による
  単位輸送コストの割引を表す。
- **経路(起点ハブ→終点ハブ)の整合性**: 各拠点間フローが実際に割り当てられた
  ハブ経由で流れることを保証する(始点側・終点側それぞれの整合性制約)。

(元の学術的定式化: O'Kelly, M. E. (1987). A quadratic integer program for the location
of interacting hub facilities. European journal of operational research, 32(3), 393-404.)
"""

from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("Hub_Location")

    # 6つの物流拠点(都市)
    node_names = ["Tokyo", "Osaka", "Nagoya", "Fukuoka", "Sendai", "Sapporo"]
    n_nodes = len(node_names)
    nodes = list(range(n_nodes))

    p = 2  # 開設するハブ数(仕分け拠点の投資予算による上限)

    # 拠点間の日次荷物量(フロー) [件] — 大都市間ほど流動が大きい非対称な物流需要
    flow_matrix = [
        # Tokyo Osaka Nagoya Fukuoka Sendai Sapporo
        [0,     120,   60,    40,     50,    45],   # Tokyo
        [110,   0,     55,    50,     20,    18],   # Osaka
        [58,    52,    0,     22,     15,    12],   # Nagoya
        [38,    48,    20,    0,      10,    8],    # Fukuoka
        [48,    18,    14,    9,      0,     15],   # Sendai
        [42,    16,    11,    7,      14,    0],    # Sapporo
    ]
    flow = {(i, j): flow_matrix[i][j] for i in nodes for j in nodes}

    # 拠点間の輸送距離 [十km単位] — 実際の地理的な位置関係を概算で反映
    distance_matrix = [
        [0,   40,  26,  88,  30,  110],
        [40,  0,   16,  60,  65,  145],
        [26,  16,  0,   72,  50,  130],
        [88,  60,  72,  0,   115, 190],
        [30,  65,  50,  115, 0,   80],
        [110, 145, 130, 190, 80,  0],
    ]
    distance = {(i, j): distance_matrix[i][j] for i in nodes for j in nodes}

    alpha = 0.6  # ハブ間幹線輸送の割引係数(大口輸送によるコスト低減)

    # 変数
    # x[i, k] = 1 のとき拠点iはハブkに割り当てられる(i=kかつx=1ならkはハブとして開設)
    x = {}
    for i in nodes:
        for k in nodes:
            x[i, k] = model.addVar(vtype="B", name=f"x_{i}_{k}")

    # y[i, k, m, j] = 拠点iから拠点jへのフローのうち、ハブk→ハブm経由で運ばれる割合
    y = {}
    for i in nodes:
        for k in nodes:
            for m in nodes:
                for j in nodes:
                    y[i, k, m, j] = model.addVar(vtype="C", lb=0, name=f"y_{i}_{k}_{m}_{j}")

    # 目的関数: 収集(i→k)+幹線(k→m、割引適用)+配送(m→j)の総輸送コスト最小化
    obj = quicksum(distance[i, k] * y[i, k, m, j] * flow[i, j] +
                   alpha * distance[k, m] * y[i, k, m, j] * flow[i, j] +
                   distance[m, j] * y[i, k, m, j] * flow[i, j]
                   for i in nodes for k in nodes for m in nodes for j in nodes)
    model.setObjective(obj, "minimize")

    # 制約
    # 開設ハブ数はちょうどp個
    model.addCons(quicksum(x[k, k] for k in nodes) == p, name="p_hubs")

    if infeasible:
        model.addCons(quicksum(x[k, k] for k in nodes) == p + 10, name="inf_hubs")

    # 各拠点は必ず1つのハブに割り当てる
    for i in nodes:
        model.addCons(quicksum(x[i, k] for k in nodes) == 1, name=f"assign_{i}")

    # 開設していない拠点をハブとして割り当てることはできない
    for i in nodes:
        for k in nodes:
            model.addCons(x[i, k] <= x[k, k], name=f"open_hub_{i}_{k}")

    # 経路制約: 拠点iから拠点jへのフローは必ずどこかのハブペア経由で100%流れる
    for i in nodes:
        for j in nodes:
            model.addCons(quicksum(y[i, k, m, j] for k in nodes for m in nodes) == 1, name=f"flow_{i}_{j}")

    for i in nodes:
        for j in nodes:
            for k in nodes:
                model.addCons(quicksum(y[i, k, m, j] for m in nodes) == x[i, k], name=f"route_start_{i}_{j}_{k}")

    for i in nodes:
        for j in nodes:
            for m in nodes:
                model.addCons(quicksum(y[i, k, m, j] for k in nodes) == x[j, m], name=f"route_end_{i}_{j}_{m}")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())
    else:
        print("No optimal solution found.")

if __name__ == "__main__":
    main()
