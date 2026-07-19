"""鉄鋼連続鋳造製造スケジュール (Steel Continuous Casting Scheduling)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model, quicksum
def build_model():
    model = Model("Steel_Continuous_Casting")
    # 鋳造順序・開始時間
    s = {i: model.addVar(vtype="C", lb=0, name=f"s_{i}") for i in range(3)}
    # 連続生産 (ギャップが一定以内)
    model.addCons(s[1] >= s[0] + 45, "gap_0_1_min")
    model.addCons(s[1] <= s[0] + 50, "gap_0_1_max")
    model.addCons(s[2] >= s[1] + 45, "gap_1_2_min")
    model.addCons(s[2] <= s[1] + 50, "gap_1_2_max")
    model.setObjective(s[2], "minimize")
    model.data = {"s": s}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("EndTime:", m.getObjVal())
