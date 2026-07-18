"""区間演算(interval arithmetic)と非線形項の値域概算 (Phase 2.c)

変数の境界だけから非線形式が取り得る値域を、区間演算で包括的に(過大評価を許して)
見積もる。値域の幅が大きい項ほど、凸緩和が緩くならざるを得ず、双対境界の律速になりやすい。
solve前の静的予測であり、Phase 2.b(実際の違反ヒートマップ)と突き合わせて妥当性を確認できる。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class Interval:
    lo: float
    hi: float

    def __post_init__(self):
        if self.lo > self.hi:
            self.lo, self.hi = self.hi, self.lo

    # --- 四則(スカラーも許容) ---
    @staticmethod
    def _iv(x) -> "Interval":
        return x if isinstance(x, Interval) else Interval(float(x), float(x))

    def __add__(self, o):
        o = self._iv(o); return Interval(self.lo + o.lo, self.hi + o.hi)
    __radd__ = __add__

    def __sub__(self, o):
        o = self._iv(o); return Interval(self.lo - o.hi, self.hi - o.lo)

    def __rsub__(self, o):
        return self._iv(o).__sub__(self)

    def __mul__(self, o):
        o = self._iv(o)
        cands = [self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi]
        return Interval(min(cands), max(cands))
    __rmul__ = __mul__

    def __truediv__(self, o):
        o = self._iv(o)
        if o.lo <= 0 <= o.hi:
            raise ValueError("interval division spanning zero")
        return self.__mul__(Interval(1.0 / o.hi, 1.0 / o.lo))

    def __rtruediv__(self, o):
        return self._iv(o).__truediv__(self)

    def __neg__(self):
        return Interval(-self.hi, -self.lo)

    # --- 単調関数 ---
    def exp(self):
        return Interval(math.exp(self.lo), math.exp(self.hi))

    def pow(self, p: float):
        # p>0 かつ底が非負なら単調増加として扱う(このモデルの用途に十分)
        lo = self.lo if self.lo > 0 else 0.0
        return Interval(lo ** p, self.hi ** p)

    # --- 指標 ---
    @property
    def width(self) -> float:
        return self.hi - self.lo

    @property
    def mid(self) -> float:
        return 0.5 * (self.lo + self.hi)

    @property
    def rel_width(self) -> float:
        return self.width / (abs(self.mid) + 1.0)

    def __repr__(self):
        return f"[{self.lo:.4g}, {self.hi:.4g}]"
