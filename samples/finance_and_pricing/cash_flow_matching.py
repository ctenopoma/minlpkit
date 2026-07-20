"""キャッシュフローマッチング債券選択問題 (Cash Flow Matching Problem)

事業ストーリー
--------------
年金基金や保険会社の資産運用担当者が、将来の年限ごとに確定している負債支払い
(年金給付・保険金支払いなど)を、手持ちの候補債券群(利付債)への投資でどう
「専用化(デディケーション)」するかを決める問題である。各債券は満期までの各期に
クーポン(利息)と、満期時には元本を支払う。各期の負債を、その期までに受け取った
債券のキャッシュフロー累計(および余剰資金の再投資収益)で確実にカバーできるように
債券の購入本数(整数)を決めつつ、購入総額(=拠出すべき資金)を最小化する。
デリバティブや市場変動リスクに頼らず、確定利付債のキャッシュフローだけで負債を
機械的にヘッジできる点が、年金ALM(資産負債管理)で広く使われる理由である。

各制約の業務的意味:
- **各期のキャッシュバランス**: 当期の債券収入+前期繰越余剰金の再投資収益が、
  当期の負債支払いと当期末の繰越余剰金の合計に一致しなければならない
  (資金がショートしない=支払い不能を防ぐ)。
- **債券購入数は整数**: 債券は端数で売買できない(市場での取引単位の制約)。
- **繰越余剰金は非負**: 資金不足(マイナス残高)は許されない=負債を必ず期日通りに
  支払えることを保証する。

(元の学術的定式化: Fabozzi, F. J. (2000). Fixed income analysis. John Wiley & Sons.)
"""
from pyscipopt import Model, quicksum

def build_model(infeasible=False):
    model = Model("CashFlowMatching")

    # 10期(半年ごと、5年分)の負債支払いスケジュール [百万円]
    periods = list(range(1, 11))
    liabilities = {
        1: 80, 2: 85, 3: 90, 4: 95, 5: 130,
        6: 100, 7: 105, 8: 110, 9: 115, 10: 220,
    }

    # 候補債券: 額面100あたりの購入価格、期ごとのクーポン+満期時元本のキャッシュフロー
    bonds = ["B1", "B2", "B3", "B4", "B5", "B6", "B7"]
    bond_prices = {
        "B1": 98.0, "B2": 101.5, "B3": 99.0, "B4": 103.0,
        "B5": 97.5, "B6": 100.5, "B7": 104.5,
    }

    def coupon_schedule(coupon, maturity, face=100.0):
        """半年ごとにクーポンを支払い、満期時に元本を返す債券のCFを組み立てる。"""
        cf = {t: coupon for t in range(1, maturity + 1)}
        cf[maturity] = cf.get(maturity, 0.0) + face
        return cf

    cash_flows = {
        "B1": coupon_schedule(3.0, 3),   # 短期・低クーポン
        "B2": coupon_schedule(4.0, 5),
        "B3": coupon_schedule(3.5, 6),
        "B4": coupon_schedule(5.0, 8),
        "B5": coupon_schedule(2.5, 4),
        "B6": coupon_schedule(4.5, 9),
        "B7": coupon_schedule(5.5, 10),  # 長期・高クーポン
    }

    reinvestment_rate = 0.015  # 半期あたりの余剰資金再投資利回り

    if infeasible:
        bonds = ["B1"]  # 短期債1銘柄だけでは長期負債を賄えず必ず不可能になる

    x = {}  # 購入する債券の口数(整数、額面100単位)
    s = {}  # 各期末の繰越余剰資金

    for b in bonds:
        x[b] = model.addVar(vtype="I", name=f"bond_{b}", lb=0)

    for t in periods:
        s[t] = model.addVar(vtype="C", name=f"surplus_{t}", lb=0)

    for t in periods:
        cf_in = quicksum(cash_flows[b].get(t, 0) * x[b] for b in bonds)
        if t == 1:
            model.addCons(cf_in - s[t] == liabilities[t], name=f"balance_{t}")
        else:
            model.addCons(cf_in + (1 + reinvestment_rate) * s[t - 1] - s[t] == liabilities[t], name=f"balance_{t}")

    model.setObjective(quicksum(bond_prices[b] * x[b] for b in bonds), "minimize")

    return model

def main():
    model = build_model()
    model.optimize()
    if model.getStatus() == "optimal":
        print("Optimal value:", model.getObjVal())

if __name__ == "__main__":
    main()
