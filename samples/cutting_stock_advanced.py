"""カッティングストック問題 (アドバンスド) (Advanced Cutting Stock)

標準的なカッティングストック問題に対し、実務上の制約である
「使用する切り出しパターン（刃の配置設定）の総数の上限（段取り替え回数の削減）」および
「スリッター刃の最大数（1つのパターンで切り出せる本数の上限）」を考慮したモデルです。
すべての可能なパターンを事前に列挙した上で、使用するパターンの選択（バイナリ変数）と
各パターンの適用回数（整数変数）を同時に最適化します。
"""

from pyscipopt import Model, quicksum

def generate_patterns(W, items, max_slits):
    """幅Wの親ロールから切り出せる、スリット数制限を満たすすべての有効なパターンを列挙します。"""
    patterns = []
    n = len(items)
    widths = [w for w, _ in items]
    
    current_pattern = [0] * n
    
    def search(idx, remaining_width, current_slits):
        if idx == n:
            if sum(current_pattern) > 0:
                patterns.append(list(current_pattern))
            return
        
        # 品目idxを何本切り出すか
        w = widths[idx]
        max_possible = min(remaining_width // w, max_slits - current_slits)
        for qty in range(max_possible + 1):
            current_pattern[idx] = qty
            search(idx + 1, remaining_width - qty * w, current_slits + qty)
            current_pattern[idx] = 0

    search(0, W, 0)
    return patterns

def build_model() -> Model:
    model = Model("Advanced_Cutting_Stock")

    # ---- データ設定 ----
    W = 110  # 親ロールの幅
    
    # 切り出す品目: (幅, 需要)
    ITEMS = [
        (45, 20),
        (36, 25),
        (31, 30),
        (22, 15),
    ]
    
    # 現場制約
    MAX_SLITS = 4        # 1パターンあたりの最大切り出し本数 (スリッター刃の数制限)
    MAX_PATTERNS = 3     # 使用可能なパターンの最大種類数 (段取り回数の制限)

    # 可能なパターンの列挙
    all_patterns = generate_patterns(W, ITEMS, MAX_SLITS)
    num_p = len(all_patterns)
    
    # 十分大きな数 Big-M (各パターンの最大適用回数は、需要の最大値程度で十分)
    BIG_M = max(d for _, d in ITEMS)

    # ---- 変数定義 ----
    # x[p]: パターンpの適用回数 (整数)
    x = {}
    # y[p]: パターンpを使用するとき1 (バイナリ)
    y = {}
    for p in range(num_p):
        x[p] = model.addVar(vtype="I", lb=0, name=f"x_{p}")
        y[p] = model.addVar(vtype="B", name=f"y_{p}")

    # ---- 制約定義 ----
    # 1. 各品目の需要充足
    for i, (width, demand) in enumerate(ITEMS):
        model.addCons(
            quicksum(all_patterns[p][i] * x[p] for p in range(num_p)) >= demand,
            name=f"demand_satisfaction_{i}"
        )

    # 2. パターン使用の紐付け (x[p] > 0 ならば y[p] = 1)
    for p in range(num_p):
        model.addCons(
            x[p] <= BIG_M * y[p],
            name=f"pattern_link_{p}"
        )

    # 3. 使用するパターンの総数制限
    model.addCons(
        quicksum(y[p] for p in range(num_p)) <= MAX_PATTERNS,
        name=f"max_patterns_limit"
    )

    # ---- 目的関数 ----
    # 使用する親ロールの総本数の最小化
    total_rolls = quicksum(x[p] for p in range(num_p))
    model.setObjective(total_rolls, "minimize")

    model.data = {"x": x, "y": y, "patterns": all_patterns, "items": ITEMS}
    return model

def main() -> None:
    model = build_model()
    model.optimize()

    status = model.getStatus()
    print(f"Optimization Status: {status}")
    if status == "optimal":
        d = model.data
        print(f"Optimal Total Rolls: {model.getObjVal():.0f}")
        x = d["x"]
        y = d["y"]
        patterns = d["patterns"]
        items = d["items"]

        print("\n--- Selected Patterns & Quantities ---")
        used_count = 0
        for p in range(len(patterns)):
            x_val = model.getVal(x[p])
            if x_val > 0.1:
                used_count += 1
                pattern_desc = ", ".join(f"width {items[i][0]}:{patterns[p][i]}pcs" for i in range(len(items)) if patterns[p][i] > 0)
                trim_loss = 110 - sum(patterns[p][i] * items[i][0] for i in range(len(items)))
                print(f"  Pattern {p:3d} (Used {int(x_val):2d} times): [{pattern_desc}] (Loss: {trim_loss}mm)")
        print(f"\nTotal Selected Patterns: {used_count} (Limit: 3)")

if __name__ == "__main__":
    main()
