"""非線形制約の違反量の可視化 (Phase 2.b)

ルートLP緩和解(凸緩和を満たす点)を、真の非線形制約に代入したときの違反量を測る。
違反が集中する制約 = そこの凸緩和が最も緩い = 双対境界を押し下げる支配的ボトルネック。
Phase 3の「区分線形近似・凸包再定式化・変数境界タイト化」の対象を特定する材料になる。

SCIPのNlRow(非線形緩和行)はもとの制約名を保持する。
    getNlRowSolFeasibility(nlrow, sol) … 負なら違反(その大きさが違反量)
    getNlRowSolActivity(nlrow, sol)    … 左辺の活動値(正規化に使う)
制約ごとにスケールが桁違いなので、相対違反 = 違反量 / (|活動値| + 1) を主指標にする。
"""

from __future__ import annotations

import pandas as pd
from pyscipopt import Eventhdlr, Model, SCIP_EVENTTYPE


class _RootLPViolation(Eventhdlr):
    """最初のLP求解(ルート)時点の緩和解での非線形制約違反を捕捉する。"""

    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []
        self._done = False

    def eventinit(self):
        self.model.catchEvent(SCIP_EVENTTYPE.FIRSTLPSOLVED, self)

    def eventexit(self):
        try:
            self.model.dropEvent(SCIP_EVENTTYPE.FIRSTLPSOLVED, self)
        except Exception:
            pass

    def eventexec(self, event):
        if self._done:
            return
        m = self.model
        sol = m.createSol()
        for v in m.getVars(transformed=True):
            m.setSolVal(sol, v, v.getLPSol())
        for nr in m.getNlRows():
            name = getattr(nr, "name", None) or "?"
            try:
                feas = m.getNlRowSolFeasibility(nr, sol)
                act = m.getNlRowSolActivity(nr, sol)
            except Exception:
                continue
            viol = max(0.0, -feas)
            ctype, _, entity = name.rpartition("_")
            self.rows.append(dict(
                constraint=name,
                ctype=ctype or name,
                entity=entity or "",
                activity=act,
                violation=viol,
                rel_violation=viol / (abs(act) + 1.0),
            ))
        m.freeSol(sol)
        self._done = True

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


def collect_root_violations(model: Model) -> pd.DataFrame:
    """モデルをルートLPまで解き、緩和解での非線形制約違反のDataFrameを返す。"""
    ev = _RootLPViolation()
    model.includeEventhdlr(ev, "RootLPViolation", "captures root LP nonlinear violations")
    model.setParam("limits/nodes", 1)
    model.hideOutput()
    model.optimize()
    return ev.to_frame()


def violation_by_type(df: pd.DataFrame) -> pd.DataFrame:
    """制約タイプ別に相対違反の平均・最大・件数を集計(平均降順)。"""
    if df.empty:
        return df
    g = (df.groupby("ctype")["rel_violation"]
         .agg(mean_rel="mean", max_rel="max", n="count")
         .reset_index().sort_values("mean_rel", ascending=False))
    return g
