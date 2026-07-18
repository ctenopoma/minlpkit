"""双対境界の改善を分枝変数に帰属させる (Phase 2.c)

Phase 1(双対境界の推移)と Phase 2.b(分枝変数)を結合する。
NODEBRANCHED ごとに (時刻, ノード数, 大域双対境界, 分枝変数, 型) を記録し、
双対境界の増分 Δdual をその直前の分枝変数に帰属させる。これにより
「gap停滞を抜けた瞬間に効いた分枝(特に連続変数への空間分枝)」を特定できる。

帰属は近似(改善した区間に活動していた分枝への信用割当)だが、
spatial(空間分枝) vs discrete(離散分枝) のどちらが境界を押し上げているかの
傾向を掴むには十分。
"""

from __future__ import annotations

import time as _time

import pandas as pd
from pyscipopt import Eventhdlr, Model, SCIP_EVENTTYPE

from .tree import _branch_kind

_INF = 1e19


class AttributionCollector(Eventhdlr):
    """分枝ごとに大域双対境界と分枝変数を記録する。"""

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []
        self._t0: float | None = None

    def eventinit(self):
        self._t0 = _time.perf_counter()
        self.model.catchEvent(SCIP_EVENTTYPE.NODEBRANCHED, self)

    def eventexit(self):
        self.model.dropEvent(SCIP_EVENTTYPE.NODEBRANCHED, self)

    def eventexec(self, event):
        m = self.model
        n = m.getCurrentNode()
        if n is None:
            return
        pb = n.getParentBranchings()
        var = kind = None
        if pb:
            v = pb[0][0]
            var, kind = v.name, _branch_kind(v.vtype())
        dual = m.getDualbound()
        self.rows.append(dict(
            time=_time.perf_counter() - self._t0,
            nodes=m.getNNodes(),
            dual=dual if abs(dual) < _INF else None,
            branch_var=var,
            kind=kind or "root",
        ))

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def attribute_gains(df: pd.DataFrame) -> pd.DataFrame:
    """各分枝レコードに、その直後の双対境界増分 Δdual を帰属させる。

    レコード i の分枝が、i→i+1 の大域双対境界の押し上げに寄与したとみなす。
    """
    if df.empty or "dual" not in df.columns:
        return pd.DataFrame(columns=["time", "nodes", "dual", "branch_var", "kind", "dual_gain"])
    d = df.dropna(subset=["dual"]).sort_values("time").reset_index(drop=True).copy()
    # 次レコードとの双対境界差(押し上げ分のみ、負や数値誤差は0に)
    d["dual_gain"] = (d["dual"].shift(-1) - d["dual"]).clip(lower=0).fillna(0.0)
    return d


def gain_by_variable(d: pd.DataFrame, top: int = 12) -> pd.DataFrame:
    g = (d.groupby(["branch_var", "kind"], dropna=False)["dual_gain"]
         .sum().reset_index().sort_values("dual_gain", ascending=False))
    return g[g["dual_gain"] > 0].head(top)


def gain_by_kind(d: pd.DataFrame) -> pd.DataFrame:
    return (d.groupby("kind")["dual_gain"].sum().reset_index()
            .sort_values("dual_gain", ascending=False))


def detect_stalls(d: pd.DataFrame, n_grid: int = 120, slow_frac: float = 0.5,
                  min_stall_frac: float = 0.06) -> list[tuple[float, float]]:
    """双対境界の改善が鈍化した時間区間を返す(横ばいではなく「平均より遅い」区間)。

    時間を等間隔グリッドに載せて双対境界を補間し、セルごとの改善量が
    平均セル改善量の slow_frac 未満のセルを「鈍化」とみなす。連続する鈍化セルを
    まとめ、全求解時間の min_stall_frac を超える区間だけ返す。
    """
    import numpy as np

    dd = d.dropna(subset=["dual"])
    if dd.empty or dd["time"].iloc[-1] <= dd["time"].iloc[0]:
        return []
    t0, t1 = dd["time"].iloc[0], dd["time"].iloc[-1]
    grid = np.linspace(t0, t1, n_grid + 1)
    # 双対境界は非減少とみなして累積最大で補間(数値ノイズを除く)
    dual_mono = np.maximum.accumulate(dd["dual"].to_numpy())
    dual_grid = np.interp(grid, dd["time"].to_numpy(), dual_mono)
    cell_gain = np.diff(dual_grid)
    total_gain = cell_gain.sum()
    if total_gain <= 0:
        return []
    avg_cell = total_gain / n_grid
    slow = cell_gain < slow_frac * avg_cell

    stall_thr = (t1 - t0) * min_stall_frac
    stalls, i = [], 0
    while i < n_grid:
        if slow[i]:
            j = i
            while j < n_grid and slow[j]:
                j += 1
            a, b = grid[i], grid[j]
            if b - a >= stall_thr:
                stalls.append((float(a), float(b)))
            i = j
        else:
            i += 1
    return stalls


def solve_and_attribute(model: Model, time_limit: float | None = None,
                        gap_limit: float | None = None) -> tuple[pd.DataFrame, dict]:
    col = AttributionCollector()
    model.includeEventhdlr(col, "AttributionCollector", "attributes dual gains")
    model.setParam("timing/clocktype", 2)
    if time_limit is not None:
        model.setParam("limits/time", time_limit)
    if gap_limit is not None:
        model.setParam("limits/gap", gap_limit)
    model.hideOutput()
    model.optimize()
    d = attribute_gains(col.to_frame())
    summary = dict(
        status=str(model.getStatus()),
        gap=model.getGap() if model.getGap() < _INF else None,
        nodes=model.getNNodes(),
        time=model.getSolvingTime(),
    )
    return d, summary
