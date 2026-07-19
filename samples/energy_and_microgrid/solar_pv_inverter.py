"""太陽光インバータ無効電力最適化 (Solar PV Inverter Reactive Power)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Solar_PV_Inverter")
    # 有効電力 P, 無効電力 Q, 皮相電力 S=P^2+Q^2 (非線形)
    p = model.addVar(vtype="C", lb=0, ub=10, name="p")
    q = model.addVar(vtype="C", lb=-5, ub=5, name="q")
    s_limit = 10.0
    model.addCons(p * p + q * q <= s_limit * s_limit, "apparent_power_limit")
    model.setObjective(p, "maximize")
    model.data = {"p": p, "q": q}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max Active Power:", m.getObjVal())
