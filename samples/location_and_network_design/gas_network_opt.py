"""天然ガスパイプライン圧力最適化 (Gas Network Optimization - MINLP)

実務問題ベースの数理最適化サンプルモデルです。
"""

from pyscipopt import Model
def build_model():
    model = Model("Gas_Network_Optimization")
    # 簡易ガスパイプライン圧力・流量(双線形)
    flow = model.addVar(vtype="C", lb=0, name="flow")
    pres_in = model.addVar(vtype="C", lb=10, ub=50, name="pres_in")
    pres_out = model.addVar(vtype="C", lb=5, ub=40, name="pres_out")
    # flow^2 = pres_in - pres_out
    model.addCons(flow * flow == pres_in - pres_out, "pipeline_pressure_loss")
    model.addCons(flow >= 3, "demand")
    model.setObjective(pres_in, "minimize")
    model.data = {"flow": flow, "pres_in": pres_in, "pres_out": pres_out}
    return model
if __name__ == "__main__":
    m = build_model(); m.optimize(); print("Min Pressure In:", m.getObjVal())
