"""SCIP探索プロセスのイベント駆動ログ収集 (Phase 1)

Eventhdlr で BESTSOLFOUND / NODESOLVED を捕捉し、
時刻・primal/dual bound・ノード数・解の由来を DataFrame に構造化する。
ログのパースではなくAPI直接取得(ノートの gurobi-logtools 方針)。
"""

from __future__ import annotations

import time as _time

import pandas as pd
from pyscipopt import Eventhdlr, Model, SCIP_EVENTTYPE

from .capture import capture_run_conditions
from .run_logger import RunLogger

_INF = 1e19  # SCIPの無限大(1e20)の判定しきい値


def _clean(v: float) -> float | None:
    return None if abs(v) >= _INF else v


class SolveMonitor(Eventhdlr):
    """探索イベントを行として蓄積するイベントハンドラ。

    - BESTSOLFOUND: 必ず記録(event='incumbent')
    - NODESOLVED / LPSOLVED: 前回記録から min_interval 秒以上経過していたら記録
      (LPSOLVEDはルートノードのカット分離ラウンドの進捗を拾うために必要)
    時刻はSCIPのクロックがWindowsで1秒粒度のため、Python側のwall clockで記録する。

    Args:
        min_interval: node/LP イベントを記録する最小間隔 [秒]。暫定解更新は常に記録。
        logger: 追記先の `RunLogger`。``None`` ならメモリのみ(バッチ用)。
    """

    EVENTS = SCIP_EVENTTYPE.BESTSOLFOUND | SCIP_EVENTTYPE.NODESOLVED | SCIP_EVENTTYPE.LPSOLVED

    def __init__(self, min_interval: float = 0.05, logger: RunLogger | None = None):
        super().__init__()
        self.min_interval = min_interval
        self.logger = logger  # 追記先(Noneならメモリのみ=バッチ用)
        self.rows: list[dict] = []
        self._last_t = -1.0
        self._t0: float | None = None

    def eventinit(self):
        self._t0 = _time.perf_counter()
        self.model.catchEvent(self.EVENTS, self)

    def eventexit(self):
        self.model.dropEvent(self.EVENTS, self)

    def eventexec(self, event):
        m = self.model
        is_sol = event.getType() == SCIP_EVENTTYPE.BESTSOLFOUND
        t = _time.perf_counter() - self._t0
        if not is_sol and t - self._last_t < self.min_interval:
            return
        self._last_t = t

        record = dict(
            time=t,
            nodes=m.getNNodes(),
            primal=_clean(m.getPrimalbound()),
            dual=_clean(m.getDualbound()),
            gap=m.getGap() if m.getGap() < _INF else None,
            event="incumbent" if is_sol else "node",
            nsols=m.getNSols(),
        )
        self.rows.append(record)
        if self.logger is not None:
            self.logger.append(record)

    def to_frame(self) -> pd.DataFrame:
        """蓄積した全イベントを DataFrame にして返す。"""
        return pd.DataFrame(self.rows)


def solve_with_monitor(
    model: Model, time_limit: float | None = None, gap_limit: float | None = None,
    min_interval: float = 0.05, logger: RunLogger | None = None,
    capture: bool = True,
) -> tuple[SolveMonitor, dict]:
    """モデルにモニタを取り付けて求解し、``(モニタ, サマリ)`` を返す。

    任意の ``pyscipopt.Model`` に使える問題非依存のドライバ。`logger` を渡すと
    探索イベントを run ディレクトリへ逐次追記し、求解後に summary を書き出す
    (`minlpkit.live.server` がライブ tail できる)。

    Args:
        model: 求解対象の ``pyscipopt.Model``。
        time_limit: 制限時間 [秒]。``None`` なら無制限。
        gap_limit: 停止する相対 gap(例 ``0.01`` で 1%)。``None`` なら最適まで。
        min_interval: node/LP イベントの最小記録間隔 [秒]。
        logger: 追記先の `RunLogger`。``None`` ならメモリのみ。
        capture: ``True`` かつ ``logger`` があるとき、求解直前に
            `capture_run_conditions` で run 条件(SCIP パラメータ差分・モデル指紋・
            環境・git SHA)を集めて ``meta.json`` の ``capture`` キーへ保存する。

    Returns:
        ``(SolveMonitor, summary)`` のタプル。``summary`` は status / objective /
        primal / dual / gap / nodes / time / nsols を含む dict。
    """
    mon = SolveMonitor(min_interval=min_interval, logger=logger)
    model.includeEventhdlr(mon, "SolveMonitor", "collects bound trajectory")
    # Windowsの既定CPUクロックは1秒粒度のため、wall clock(細粒度)に切り替える
    model.setParam("timing/clocktype", 2)
    if time_limit is not None:
        model.setParam("limits/time", time_limit)
    if gap_limit is not None:
        model.setParam("limits/gap", gap_limit)
    # run 条件の自動キャプチャ(パラメータ設定後・optimize前の状態を残す)。
    # 失敗しても求解は止めない。
    if capture and logger is not None:
        try:
            logger.update_meta({"capture": capture_run_conditions(model)})
        except Exception:  # noqa: BLE001 - キャプチャ失敗で求解を止めない
            pass
    model.optimize()
    summary = dict(
        status=model.getStatus(),
        objective=_clean(model.getObjVal()) if model.getNSols() > 0 else None,
        primal=_clean(model.getPrimalbound()),
        dual=_clean(model.getDualbound()),
        gap=model.getGap() if model.getGap() < _INF else None,
        nodes=model.getNNodes(),
        time=model.getSolvingTime(),
        nsols=model.getNSols(),
    )
    if logger is not None:
        logger.finish({**summary, "status": str(summary["status"])})
    return mon, summary


def primal_gap_series(df: pd.DataFrame, ref: float | None) -> pd.DataFrame:
    """primal gap p(t) と Primal Integral の累積値を計算する。

    ``p(t) = |primal(t) − ref| / max(|primal(t)|, |ref|)``、解なしは 1 (Achterberg流)。

    Args:
        df: `SolveMonitor.to_frame` の出力(``time`` / ``primal`` 列を使う)。
        ref: 基準となる最終 primal 値。``None`` や空 df なら空表を返す。

    Returns:
        ``time`` / ``pgap`` / ``pintegral`` を持つ DataFrame。
    """
    if ref is None or df.empty:
        return pd.DataFrame(columns=["time", "pgap", "pintegral"])
    d = df[["time", "primal"]].copy()
    denom = d["primal"].abs().clip(lower=abs(ref))
    d["pgap"] = ((d["primal"] - ref).abs() / denom).fillna(1.0).clip(upper=1.0)
    # 区分定数(左側の値が次の時刻まで持続)として積分
    dt = d["time"].diff().shift(-1).fillna(0.0)
    d["pintegral"] = (d["pgap"] * dt).cumsum()
    return d[["time", "pgap", "pintegral"]]
