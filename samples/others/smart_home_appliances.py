"""スマートホーム家電個別制御スケジュール (Smart Home Appliances)

事業ストーリー
--------------
家庭用エネルギーマネジメントシステム(HEMS)が、複数の家電(食洗機・洗濯機・EV充電器等)
の稼働時間帯を、時間帯別電気料金が最も安くなるように自動決定する意思決定である。各家電は
所定の連続稼働時間数を1日の中のどこかに割り当てる必要があり、家庭の契約ブレーカー容量
(同時使用可能な最大消費電力)を各時間帯で超えてはならない。さらに一部家電(洗濯機など)
は稼働完了希望時刻(利用者が翌朝までに乾燥まで終わらせたい、等)の制約を持つ。HEMSは、
契約容量制約と各家電の完了時刻制約を満たしながら、1日の総電気代を最小化する運転
スケジュールを決める。
"""

from pyscipopt import Model, quicksum

SCALES = {
    "small": dict(n_appliance=3, n_period=6),
    "default": dict(n_appliance=4, n_period=8),
    "large": dict(n_appliance=6, n_period=10),
}


def build_model(scale: str = "default") -> Model:
    cfg = SCALES[scale]
    n_appliance, n_period = cfg["n_appliance"], cfg["n_period"]
    appliances, periods = range(n_appliance), range(n_period)

    # 時間帯別電気料金(円/kWh、深夜安・日中高のシンプルな日内パターン)
    base_prices = [10, 8, 8, 12, 18, 20, 18, 12, 10, 8]
    prices = [base_prices[t % len(base_prices)] for t in periods]

    run_hours = {a: 2 + (a % 2) for a in appliances}  # 家電ごとの連続稼働時間数
    power_kw = {a: 1.0 + 0.5 * a for a in appliances}  # 家電ごとの消費電力
    breaker_limit = 4.5  # 契約ブレーカー容量 [kW]
    deadline = {a: n_period - (a % 2) for a in appliances}  # 稼働完了希望期限(期の番号)

    model = Model("Smart_Home_Appliances")

    x = {(a, t): model.addVar(vtype="B", name=f"x_{a}_{t}") for a in appliances for t in periods}

    for a in appliances:
        # 各家電は所定の連続稼働時間数だけ動作する
        model.addCons(quicksum(x[a, t] for t in periods) == run_hours[a], name=f"run_time_{a}")
        # 完了希望期限を超える時間帯には稼働させない
        for t in periods:
            if t >= deadline[a]:
                model.addCons(x[a, t] == 0, name=f"deadline_{a}_{t}")

    for t in periods:
        # 契約ブレーカー容量: 同時刻に動作する家電の消費電力合計が上限を超えない
        model.addCons(
            quicksum(x[a, t] * power_kw[a] for a in appliances) <= breaker_limit, name=f"breaker_{t}")

    model.setObjective(
        quicksum(x[a, t] * prices[t] * power_kw[a] for a in appliances for t in periods), "minimize")
    model.data = {"x": x, "dims": (n_appliance, n_period)}
    return model


if __name__ == "__main__":
    m = build_model("small")
    m.optimize()
    print("status:", m.getStatus())
    if m.getNSols() > 0:
        print("Cost:", m.getObjVal())
