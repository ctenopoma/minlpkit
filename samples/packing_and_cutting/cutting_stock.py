"""カッティングストック問題 — 列生成の実証用

幅Wのロールから、幅w_iの品目を需要d_i本切り出す。使うロール本数を最小化。
コンパクト定式化(Kantorovich)はLP緩和が弱く対称性も強い。列生成(Gilmore-Gomory)は
「切り出しパターン」を列とし、価格付け(pricing)ナップサックで列を追加する。
GGのLP緩和は「材料下界」に一致し、コンパクト定式化より格段に強い。
"""

from __future__ import annotations

from pyscipopt import Model, quicksum

W = 100  # ロール幅
# (幅, 需要)
ITEMS = [(45, 12), (36, 15), (31, 10), (27, 14), (14, 20), (19, 16)]
WIDTHS = [w for w, _ in ITEMS]
DEMANDS = [d for _, d in ITEMS]
N_ITEMS = len(ITEMS)
MAX_ROLLS = sum((W // w) and (d + w - 1) // (W // w) or d for (w, d) in ITEMS)  # 粗い上限


def build_compact() -> Model:
    """コンパクト定式化(Kantorovich): ロールrごとに品目を割り当てる。"""
    m = Model("cutting_stock_compact")
    R = sum(DEMANDS)  # ロール本数の上限(各品目1本ずつでも足りる粗い上限)
    R = min(R, 60)
    y = {r: m.addVar(vtype="B", name=f"y_{r}") for r in range(R)}
    a = {(i, r): m.addVar(vtype="I", lb=0, name=f"a_{i}_{r}")
         for i in range(N_ITEMS) for r in range(R)}
    for i in range(N_ITEMS):
        m.addCons(quicksum(a[i, r] for r in range(R)) >= DEMANDS[i], name=f"demand_{i}")
    for r in range(R):
        m.addCons(quicksum(WIDTHS[i] * a[i, r] for i in range(N_ITEMS)) <= W * y[r],
                  name=f"width_{r}")
    m.setObjective(quicksum(y[r] for r in range(R)), "minimize")
    m.data = dict(y=y, a=a, R=R)
    return m


if __name__ == "__main__":
    m = build_compact()
    m.hideOutput()
    m.setParam("limits/time", 20)
    m.optimize()
    print(f"compact: status={m.getStatus()} rolls={m.getObjVal():.0f} nodes={m.getNNodes()}")
