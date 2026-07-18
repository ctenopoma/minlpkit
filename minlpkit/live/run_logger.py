"""Run ログの書き手 (TensorBoard の SummaryWriter 相当)

ソルバー(書き手)は run ディレクトリに追記するだけ。読み手(server.py)は
そのファイルを tail する。両者はプロセスもファイルも介してのみ結合する。

<cwd>/results/runs/<run_id>/
    meta.json      … run開始時に1回。model/title/params/created/status="running"
    events.jsonl   … 探索イベント1件=1行(追記・逐次flush)
    summary.json   … 求解終了時に1回。最終status/obj/gap/nodes/time

出力先は「実行時のカレントディレクトリ配下 `results/runs/`」に固定する。
配布パッケージとして別プロジェクトから使う場合も、そのプロジェクトの作業
ディレクトリにログが出る(site-packages 内に書かない)。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

RUNS_ROOT = Path.cwd() / "results" / "runs"


def new_run_id(model: str) -> str:
    """`<model>_<YYYYmmdd_HHMMSS>` 形式の一意な run_id を生成する。

    Args:
        model: モデル識別子(例: ``"plant"``)。生成される run_id の接頭辞になる。

    Returns:
        run ディレクトリ名に使える文字列。
    """
    return f"{model}_{datetime.now():%Y%m%d_%H%M%S}"


class RunLogger:
    """1回の求解に対応する追記ロガー。

    生成時に run ディレクトリを作り ``meta.json`` を書き、``events.jsonl`` を
    行バッファ + 明示 flush で開く。読み手(server.py)がリアルタイムに tail
    できるよう、`append` のたびに flush する。

    Args:
        run_id: run の一意識別子(`new_run_id` で生成)。
        meta: run のメタ情報(model / title / params 等)。``run_id`` /
            ``created`` / ``status`` は自動付与される。
        root: run ディレクトリの親。既定は `RUNS_ROOT`(``<cwd>/results/runs``)。

    Example:
        >>> from minlpkit.live import RunLogger, new_run_id
        >>> rid = new_run_id("demo")
        >>> logger = RunLogger(rid, meta={"model": "demo", "title": "t"})  # doctest: +SKIP
    """

    def __init__(self, run_id: str, meta: dict, root: Path = RUNS_ROOT):
        self.run_id = run_id
        self.dir = root / run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = {**meta, "run_id": run_id, "created": datetime.now().isoformat(timespec="seconds"),
                "status": "running"}
        self._write_json("meta.json", meta)
        # 行バッファ + 明示flushで、読み手が即座に tail できるようにする
        self._f = open(self.dir / "events.jsonl", "w", encoding="utf-8", buffering=1)

    def _write_json(self, name: str, obj: dict) -> None:
        (self.dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def append(self, record: dict) -> None:
        """探索イベント1件を ``events.jsonl`` に1行追記して flush する。

        Args:
            record: 1イベント分の観測量(time / primal / dual / gap 等)。
        """
        self._f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._f.flush()

    def finish(self, summary: dict) -> None:
        """求解サマリを ``summary.json`` に書き、イベントファイルを閉じる。

        Args:
            summary: 最終 status / objective / gap / nodes / time 等。``run_id``
                と ``finished`` タイムスタンプが自動付与される。
        """
        summary = {**summary, "run_id": self.run_id,
                   "finished": datetime.now().isoformat(timespec="seconds")}
        self._write_json("summary.json", summary)
        self._f.close()
