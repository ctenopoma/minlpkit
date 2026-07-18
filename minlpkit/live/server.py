"""Run ログの読み手 — Flask + SSE ライブ配信サーバ (TensorBoard 相当)

書き手(run_monitor.py)が results/runs/<id>/ に追記するイベントを tail し、
SSE でブラウザにライブ push する。書き手とはファイルのみを介して結合する。

起動: uv run python -m minlpkit.live.server   → http://127.0.0.1:5000
      (後方互換: uv run python -m viz.server も同じサーバを起動)
ソルバは別ターミナルで: uv run python experiments/run_monitor.py --model plant --time 120

このモジュールは flask / plotly を必要とする(`minlpkit[viz]` extra)。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

try:
    from flask import Flask, Response, jsonify, send_from_directory
    from plotly.offline import get_plotlyjs
except ModuleNotFoundError as _e:  # pragma: no cover - extras 未導入時の案内
    raise ModuleNotFoundError(
        "minlpkit.live のライブサーバには flask / plotly が必要です。"
        '`uv add "minlpkit[viz]"` で導入してください。'
    ) from _e

from .run_logger import RUNS_ROOT

RESULTS_ROOT = RUNS_ROOT.parent  # results/ (runs/ はこの直下)

app = Flask(__name__)
_PAGE = (Path(__file__).parent / "live_page.html").read_text(encoding="utf-8")
_PLOTLYJS = get_plotlyjs()


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@app.route("/")
def index() -> Response:
    return Response(_PAGE, mimetype="text/html")


@app.route("/plotly.js")
def plotlyjs() -> Response:
    # オフライン配信(CDN不要)。長期キャッシュ可
    return Response(_PLOTLYJS, mimetype="application/javascript",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.route("/api/runs")
def list_runs() -> Response:
    """run 一覧を新しい順で返す。run セレクタ表示用に summary の gap/primal/dual/nodes も混ぜ込む。"""
    runs = []
    if RUNS_ROOT.exists():
        for d in RUNS_ROOT.iterdir():
            meta = _read_json(d / "meta.json") if d.is_dir() else None
            if meta is None:
                continue
            summary = _read_json(d / "summary.json")
            meta["status"] = summary["status"] if summary else meta.get("status", "running")
            for key in ("gap", "primal", "dual", "nodes"):
                meta[key] = summary.get(key) if summary else None
            runs.append(meta)
    runs.sort(key=lambda m: m.get("created", ""), reverse=True)
    return jsonify(runs)


@app.route("/api/runs/<run_id>/events")
def run_events(run_id: str) -> Response:
    """指定runの meta/events(全件)/summary を一括で返す(比較モード用)。

    完了済みrunの再取得だけでなく、進行中runの現時点スナップショットにも使える。
    ライブ購読(SSE)の代わりにはならない — 単一runのリアルタイム表示は /stream を使う。
    """
    run_dir = (RUNS_ROOT / run_id).resolve()
    if RUNS_ROOT.resolve() not in run_dir.parents:  # パストラバーサル防止
        return Response("invalid run id", status=400)
    meta = _read_json(run_dir / "meta.json")
    if meta is None:
        return Response("run not found", status=404)
    events: list[dict] = []
    events_path = run_dir / "events.jsonl"
    if events_path.exists():
        # tail中の書き込み途中行(改行なし)を除くのはstream()と同じ扱い
        lines = events_path.read_text(encoding="utf-8").split("\n")
        for line in lines[:-1]:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    summary = _read_json(run_dir / "summary.json")
    return jsonify({"meta": meta, "events": events, "summary": summary})


@app.route("/results/<path:filename>")
def results_file(filename: str) -> Response:
    """results/ 配下の静的HTML(成果物ギャラリー等)を配信する。"""
    target = (RESULTS_ROOT / filename).resolve()
    if RESULTS_ROOT.resolve() not in target.parents:  # パストラバーサル防止
        return Response("invalid path", status=400)
    if not target.is_file():
        return Response("not found", status=404)
    return send_from_directory(RESULTS_ROOT.resolve(), filename)


@app.route("/api/runs/<run_id>/stream")
def stream(run_id: str) -> Response:
    """events.jsonl を tail し、新規行を SSE で流す。summary 出現で done を送って終了。"""
    run_dir = (RUNS_ROOT / run_id).resolve()
    if RUNS_ROOT.resolve() not in run_dir.parents:  # パストラバーサル防止
        return Response("invalid run id", status=400)
    events_path = run_dir / "events.jsonl"
    summary_path = run_dir / "summary.json"

    def gen():
        emitted = 0
        idle = 0.0
        while True:
            complete = []
            if events_path.exists():
                # 末尾が改行なしの途中書き行なら最後の要素は不完全 → 除外
                lines = events_path.read_text(encoding="utf-8").split("\n")
                complete = lines[:-1]
            for line in complete[emitted:]:
                if line.strip():
                    yield f"data: {line}\n\n"
            if len(complete) > emitted:
                emitted = len(complete)
                idle = 0.0

            summary = _read_json(summary_path)
            if summary is not None and emitted >= len(complete):
                yield f"event: done\ndata: {json.dumps(summary, ensure_ascii=False)}\n\n"
                return

            time.sleep(0.4)
            idle += 0.4
            if idle > 900:  # 15分無進捗(サーバ再起動等で summary が来ないケース)で打ち切り
                yield "event: done\ndata: {\"status\": \"stream timeout\"}\n\n"
                return

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def main() -> None:
    """ライブ配信サーバを http://127.0.0.1:5000 で起動する。"""
    # threaded=True: SSEの長時間コネクションと /api/runs 等を同時に捌く
    app.run(host="127.0.0.1", port=5000, threaded=True, debug=False)


if __name__ == "__main__":
    main()
