"""バス運転士勤務表自動生成 (Bus Driver Rostering)

事業ストーリー
--------------
バス営業所の運行管理者が、1週間分の運転士シフトを決める。曜日ごとに必要な出勤人数
(平日は通勤需要で多く、週末は少ない)を満たしつつ、労働基準(週の最大勤務日数・
最低週休日数)を守った勤務表を組む必要がある。

各制約の業務的意味:
- **曜日ごとの必要出勤人数**: 各曜日で運行に必要な最低人数の運転士を確保しなければ
  便を減らさざるを得ない。
- **週の最大勤務日数**: 労働基準法・労使協定により、1人の運転士が週に働ける日数には
  上限がある。
- **週休の下限**: 全運転士が週に最低1日は休みを取れるようにする(過重労働防止)。
- **人件費最小化**: 曜日・運転士によらず一律の日当だが、出勤日数が増えるほど
  総人件費が増える。
"""
from __future__ import annotations

from pyscipopt import Model, quicksum

DRIVERS = ["driver_A", "driver_B", "driver_C", "driver_D", "driver_E"]
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
REQUIRED = {"mon": 3, "tue": 3, "wed": 3, "thu": 3, "fri": 4, "sat": 2, "sun": 2}
DAILY_WAGE = 180
MAX_WORK_DAYS = 5
MIN_REST_DAYS = 1


def build_model():
    model = Model("Bus_Driver_Rostering")

    x = {(d, day): model.addVar(vtype="B", name=f"x_{d}_{day}")
         for d in DRIVERS for day in DAYS}

    for day in DAYS:
        model.addCons(quicksum(x[d, day] for d in DRIVERS) >= REQUIRED[day],
                       f"coverage_{day}")

    for d in DRIVERS:
        model.addCons(quicksum(x[d, day] for day in DAYS) <= MAX_WORK_DAYS,
                       f"max_work_{d}")
        model.addCons(quicksum(1 - x[d, day] for day in DAYS) >= MIN_REST_DAYS,
                       f"min_rest_{d}")

    model.setObjective(DAILY_WAGE * quicksum(x[d, day] for d in DRIVERS for day in DAYS),
                        "minimize")
    model.data = {"x": x}
    return model


if __name__ == "__main__":
    m = build_model()
    m.optimize()
    print("Weekly Labor Cost:", m.getObjVal())
