"""空間分枝木の収集と可視化 (Phase 2.b)

NODEBRANCHED で分枝ノードを収集し、各ノードの
    番号 / 親 / 深さ / 下界(=そのノードの双対境界) / 分枝変数と型
を記録する。MINLP固有の観点として、分枝変数の型で
    spatial(連続変数への空間分枝) / integer / binary
を色分けし、非凸緩和を締める空間分枝が木のどこで起きているかを見せる。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyscipopt import Eventhdlr, Model, SCIP_EVENTTYPE

_INF = 1e19


def _branch_kind(vtype: str | None) -> str:
    if vtype is None:
        return "root"
    if vtype in ("BINARY",):
        return "binary"
    if vtype in ("INTEGER", "IMPLINT"):
        return "integer"
    return "spatial"  # CONTINUOUS → 空間分枝(MINLP固有)


class TreeCollector(Eventhdlr):
    """分枝ノードを収集する。incumbent発見ノードも記録する。"""

    EVENTS = SCIP_EVENTTYPE.NODEBRANCHED | SCIP_EVENTTYPE.BESTSOLFOUND

    def __init__(self, max_nodes: int = 500):
        super().__init__()
        self.max_nodes = max_nodes
        self.rows: list[dict] = []
        self.incumbent_nodes: set[int] = set()

    def eventinit(self):
        self.model.catchEvent(self.EVENTS, self)

    def eventexit(self):
        self.model.dropEvent(self.EVENTS, self)

    def eventexec(self, event):
        m = self.model
        if event.getType() == SCIP_EVENTTYPE.BESTSOLFOUND:
            node = m.getCurrentNode()
            if node is not None:
                self.incumbent_nodes.add(node.getNumber())
            return
        if len(self.rows) >= self.max_nodes:
            return
        n = m.getCurrentNode()
        if n is None:
            return
        pb = n.getParentBranchings()
        var = vtype = None
        bound = btype = None
        if pb:
            v = pb[0][0]
            var, vtype = v.name, v.vtype()
            bound, btype = pb[1][0], pb[2][0]
        lb = n.getLowerbound()
        parent = n.getParent()
        self.rows.append(dict(
            node=n.getNumber(),
            parent=parent.getNumber() if parent is not None else None,
            depth=n.getDepth(),
            lowerbound=lb if abs(lb) < _INF else None,
            branch_var=var,
            kind=_branch_kind(vtype),
            bound=bound,
            btype=("<=" if btype == 1 else ">=") if btype is not None else None,
        ))

    def to_frame(self) -> pd.DataFrame:
        df = pd.DataFrame(self.rows)
        if not df.empty:
            df["incumbent"] = df["node"].isin(self.incumbent_nodes)
        return df


def layout_tree(df: pd.DataFrame) -> pd.DataFrame:
    """tidy tree レイアウト。x=葉のDFS順で確定、内部ノード=子の平均、y=-depth。"""
    children: dict[int, list[int]] = {}
    for _, r in df.iterrows():
        children.setdefault(r["parent"], []).append(r["node"])
    # 子は node 番号順(生成順に近い)で並べる
    for k in children:
        children[k].sort()

    roots = df.loc[df["parent"].isna(), "node"].tolist()
    if not roots:  # 親が収集外なら最小深さを根扱い
        roots = [df.sort_values("depth").iloc[0]["node"]]

    xpos: dict[int, float] = {}
    counter = [0]

    def assign(node: int) -> float:
        kids = children.get(node, [])
        if not kids:
            x = float(counter[0])
            counter[0] += 1
        else:
            xs = [assign(c) for c in kids]
            x = float(np.mean(xs))
        xpos[node] = x
        return x

    for root in roots:
        assign(root)

    df = df.copy()
    df["x"] = df["node"].map(xpos)
    df["y"] = -df["depth"]
    return df


def solve_and_collect(model: Model, max_nodes: int = 500,
                      node_limit: int | None = None) -> pd.DataFrame:
    col = TreeCollector(max_nodes=max_nodes)
    model.includeEventhdlr(col, "TreeCollector", "collects branch tree")
    model.setParam("timing/clocktype", 2)
    if node_limit is not None:
        model.setParam("limits/nodes", node_limit)
    model.hideOutput()
    model.optimize()
    return layout_tree(col.to_frame())
