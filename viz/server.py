"""後方互換シム: 実体は minlpkit.live.server へ移設済み。

`uv run python -m viz.server` での起動を引き続き動かすための薄い再エクスポート。
新規コードは `minlpkit.live.server`(`python -m minlpkit.live.server`)を使うこと。
"""
from minlpkit.live.server import *  # noqa: F401,F403
from minlpkit.live import server as _impl  # noqa: F401


def __getattr__(name):
    return getattr(_impl, name)


if __name__ == "__main__":
    _impl.main()
