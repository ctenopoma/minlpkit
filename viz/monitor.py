"""後方互換シム: 実体は minlpkit.live.monitor へ移設済み。

既存の experiments/run_*.py が `from viz.monitor import ...` のまま動き続ける
ための薄い再エクスポート。新規コードは `minlpkit.live` を直接使うこと。
"""
from minlpkit.live.monitor import *  # noqa: F401,F403
from minlpkit.live import monitor as _impl  # noqa: F401


def __getattr__(name):
    return getattr(_impl, name)
