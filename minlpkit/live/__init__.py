"""minlpkit.live — 任意の ``pyscipopt.Model`` に使える問題非依存のライブ可視化。

TensorBoard 型(書き手/読み手分離)の求解モニタ。書き手 `solve_with_monitor` /
`RunLogger` が ``<cwd>/results/runs/<run_id>/`` にイベントを追記し、読み手
`minlpkit.live.server`(Flask + SSE)がそれを tail してブラウザへライブ push する。
バッチ用途では `build_dashboard` で単一 HTML ダッシュボードも出せる。
`sweep` / `rerun` はパラメータ探索を「通常の run」として記録する(runs一覧UIが
そのまま比較UIになる)。

この機能は追加依存(flask / plotly / kaleido)を要する。extras 未導入で
``import minlpkit.live`` すると、導入方法を案内する ImportError を送出する::

    uv add "minlpkit[viz]"

コア(`import minlpkit`)は extras 無しで動く。
"""

from .capture import capture_run_conditions
from .monitor import SolveMonitor, primal_gap_series, solve_with_monitor
from .plots import build_dashboard
from .run_logger import RUNS_ROOT, RunLogger, new_run_id
from .server import app, main
from .sweep import rerun, sweep

__all__ = [
    "SolveMonitor",
    "solve_with_monitor",
    "primal_gap_series",
    "capture_run_conditions",
    "RunLogger",
    "new_run_id",
    "RUNS_ROOT",
    "build_dashboard",
    "app",
    "main",
    "sweep",
    "rerun",
]
