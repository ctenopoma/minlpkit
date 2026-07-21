"""後方互換シム: 実体は minlpkit.collectors.infeasibility へ移設済み。

新規コードは minlpkit を直接使うこと(mk.diagnose_infeasibility / elastic_filter /
deletion_filter)。
"""
from minlpkit.collectors.infeasibility import *  # noqa: F401,F403
from minlpkit.collectors import infeasibility as _impl  # noqa: F401


def __getattr__(name):
    return getattr(_impl, name)
