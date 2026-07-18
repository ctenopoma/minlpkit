"""後方互換シム: 実体は minlpkit.collectors.diagnose へ移設済み。

既存の run_*.py / demo.py / viz.server が `from viz.diagnose import ...` のまま
動き続けるための薄い再エクスポート。新規コードは minlpkit を直接使うこと。
"""
from minlpkit.collectors.diagnose import *  # noqa: F401,F403
from minlpkit.collectors import diagnose as _impl  # noqa: F401

# import * が拾わないモジュール属性(_接頭辞など)への後方互換アクセス用
def __getattr__(name):
    return getattr(_impl, name)
