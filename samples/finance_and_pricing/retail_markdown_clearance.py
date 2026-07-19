"""小売クリアランス値引き時期決定 (Retail Clearance Markdown)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Retail_Clearance_Markdown")
    # 各週に値引きを行うか (3週間)
    md = {t: model.addVar(vtype="B", name=f"md_{t}") for t in range(3)}
    model.addCons(quicksum(md[t] for t in range(3)) <= 1, "max_one_markdown")
    model.setObjective(md[0] * 500 + md[1] * 350 + md[2] * 200, "maximize")
    model.data = {"md": md}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Revenue:", m.getObjVal())
