"""後方互換シム: 実体は minlpkit.tune へ移設済み。

既存の experiments/run_tune.py が `from viz.tune import ...` のまま動き続ける
ための薄い再エクスポート。新規コードは `minlpkit.tune` を直接使うこと。
"""
from minlpkit.tune import *  # noqa: F401,F403
from minlpkit import tune as _impl  # noqa: F401


def __getattr__(name):
    return getattr(_impl, name)
