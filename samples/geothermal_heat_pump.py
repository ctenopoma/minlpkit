"""地熱ヒートポンプCOP最適化運転 (Geothermal Heat Pump)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Geothermal_Heat_Pump")
    # COP = a - b * delta_T (簡易)
    t_out = model.addVar(vtype="C", lb=30, ub=50, name="t_out")
    cop = model.addVar(vtype="C", lb=1, name="cop")
    model.addCons(cop == 6.0 - 0.05 * (t_out - 15.0), "cop_equation")
    model.addCons(t_out >= 40, "comfort")
    model.setObjective(cop, "maximize")
    model.data = {"cop": cop, "t_out": t_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Max COP:", m.getObjVal())
