"""minlpkit.otel(OTLPエクスポート)のテスト。

ネットワーク送信の代わりに OpenTelemetry SDK 付属の in-memory エクスポータへ
書き込み、span / log / metric の内容(親子関係・属性・実時刻)を検証する。
campaign は実SCIP(ablate)で生成した本物の run ディレクトリを使う。
"""
from __future__ import annotations

import json

import pytest
from opentelemetry.sdk._logs.export import InMemoryLogRecordExporter
from opentelemetry.sdk.metrics.export import MetricExporter, MetricExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from minlpkit.otel import _Exporters, export_campaign, export_run


class ListMetricExporter(MetricExporter):
    """MetricsData をメモリに積むだけの実 MetricExporter 実装(テスト用)。"""

    def __init__(self):
        super().__init__()
        self.batches = []

    def export(self, metrics_data, timeout_millis=10_000, **kwargs):
        self.batches.append(metrics_data)
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis=10_000):
        return True

    def shutdown(self, timeout_millis=30_000, **kwargs):
        pass

    def points(self):
        return [pt for md in self.batches for rm in md.resource_metrics
                for sm in rm.scope_metrics for m in sm.metrics
                for pt in m.data.data_points]


@pytest.fixture()
def exporters():
    return _Exporters(span_exporter=InMemorySpanExporter(),
                      metric_exporter=ListMetricExporter(),
                      log_exporter=InMemoryLogRecordExporter())


def _write_run(run_dir, *, created="2026-07-30T12:00:00", status="timelimit",
               gap=0.5, time=10.0, campaign=None):
    """エクスポータの入力契約(meta/events/summary)を満たす run ディレクトリを作る。"""
    run_dir.mkdir(parents=True)
    meta = {"run_id": run_dir.name, "model": "toy", "created": created,
            "status": "running"}
    if campaign:
        meta["campaign"] = campaign
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    events = [
        {"time": 0.5, "nodes": 1, "primal": None, "dual": 1.0, "gap": None, "event": "node"},
        {"time": 1.0, "nodes": 5, "primal": 3.0, "dual": 1.5, "gap": 1.0, "event": "incumbent"},
        {"time": 9.0, "nodes": 50, "primal": 2.2, "dual": 1.6, "gap": gap, "event": "node"},
    ]
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    (run_dir / "summary.json").write_text(json.dumps(
        {"status": status, "gap": gap, "nodes": 50, "time": time, "nsols": 1,
         "run_id": run_dir.name, "finished": "2026-07-30T12:00:10"}), encoding="utf-8")


def test_export_run_span_metrics_logs(tmp_path, exporters):
    """1 run のエクスポート: スパン期間・incumbentイベント・実時刻メトリクス・完了ログ。"""
    run_dir = tmp_path / "runs" / "toy_1"
    campaign = {"id": "c1", "kind": "ablation", "axis": {"off": "demand", "n_removed": 6}}
    _write_run(run_dir, campaign=campaign)

    res = export_run(run_dir, _exporters=exporters)
    assert res["run_id"] == "toy_1"
    assert res["n_events"] == 3

    # スパン: 期間が created..finished、属性に opt.* が載る
    (span,) = exporters.span.get_finished_spans()
    assert span.name == "solve toy"
    assert span.attributes["opt.run_id"] == "toy_1"
    assert span.attributes["opt.campaign_id"] == "c1"
    assert span.attributes["opt.axis.off"] == "demand"
    assert span.attributes["opt.status"] == "timelimit"
    assert (span.end_time - span.start_time) == pytest.approx(10e9)
    # incumbent 更新はスパンイベント(実時刻 = created + 1.0s)
    (inc,) = [e for e in span.events if e.name == "incumbent"]
    assert inc.timestamp - span.start_time == pytest.approx(1.0e9)
    assert inc.attributes["opt.primal"] == 3.0

    # メトリクス: gap は None を除いた2点、時刻はイベントの実時刻
    pts = exporters.metric.points()
    gap_ts = sorted(pt.time_unix_nano - span.start_time for md in exporters.metric.batches
                    for rm in md.resource_metrics for sm in rm.scope_metrics
                    for m in sm.metrics if m.name == "opt.gap"
                    for pt in m.data.data_points)
    assert gap_ts == [pytest.approx(1.0e9), pytest.approx(9.0e9)]
    assert all(pt.attributes["opt.run_id"] == "toy_1" for pt in pts)

    # ログ: 完了サマリが1件、trace と相関している
    (log,) = exporters.log.get_finished_logs()
    assert log.log_record.attributes["opt.event"] == "run_finished"
    assert log.log_record.trace_id == span.context.trace_id


def test_export_run_infeasible_is_error_status(tmp_path, exporters):
    """infeasible run はスパン status=ERROR、完了ログ severity=FATAL(critical写像)。"""
    from opentelemetry.trace import StatusCode

    run_dir = tmp_path / "runs" / "toy_inf"
    _write_run(run_dir, status="infeasible", gap=0.0)
    export_run(run_dir, _exporters=exporters)
    (span,) = exporters.span.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    (log,) = exporters.log.get_finished_logs()
    assert log.log_record.severity_text == "FATAL"


def test_export_campaign_real_ablate(tmp_path, exporters):
    """実SCIPの ablate で作った campaign を丸ごとエクスポート:
    親スパン1 + 子スパン3 が同一トレースに束なり、verdict がログで出る。"""
    from pyscipopt import Model

    from minlpkit.live import ablate

    def build():
        m = Model()
        m.hideOutput()
        x = m.addVar(lb=0, ub=10, name="x")
        m.addCons(x >= 6, name="demand_min")
        m.addCons(x <= 4, name="cap_max")
        m.setObjective(x, "minimize")
        return m

    ablate(build, {"demand": "demand", "cap": "cap"}, name="t_otel", time_limit=5,
           runs_root=tmp_path / "runs", campaigns_root=tmp_path / "campaigns")
    cdir = next((tmp_path / "campaigns").glob("t_otel_ablation_*"))

    res = export_campaign(cdir, runs_root=tmp_path / "runs", _exporters=exporters)
    assert len(res["runs"]) == 3
    assert res["n_verdicts"] == 2

    spans = exporters.span.get_finished_spans()
    parents = [s for s in spans if s.name.startswith("campaign")]
    children = [s for s in spans if not s.name.startswith("campaign")]
    assert len(parents) == 1 and len(children) == 3
    assert all(c.parent is not None and
               c.context.trace_id == parents[0].context.trace_id for c in children)

    verdicts = [l.log_record for l in exporters.log.get_finished_logs()
                if (l.log_record.attributes or {}).get("opt.event") == "verdict"]
    assert len(verdicts) == 2
    assert all(v.severity_text == "FATAL" for v in verdicts)  # critical → FATAL
    assert all(v.attributes.get("opt.recipe") for v in verdicts)
    assert all(v.trace_id == parents[0].context.trace_id for v in verdicts)
