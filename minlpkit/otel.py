"""minlpkit.otel — run / campaign の OpenTelemetry(OTLP)エクスポート(extras ``otel``)

記録済みの ``results/runs/<run_id>/``(meta / events / summary)と
``results/campaigns/<id>/campaign.json`` を OTLP の 3 シグナルへ写像して送る:

- **Trace**: campaign = 親スパン、各 run = 子スパン(incumbent 更新はスパンイベント)
- **Metrics**: gap / primal / dual / nodes をゲージとして探索イベントの実時刻で送る
- **Logs**: run 完了サマリと **verdicts(ライブラリからの提案)** を severity 付きで送る

書き手/読み手分離は維持する: ソルバーはファイルに書くだけで、本モジュールは
「ファイル → OTLP」の第二の読み手(shipper)。送信先は Grafana Alloy の OTLP 受口
(既定 ``http://localhost:4318``)を想定し、Alloy が Tempo / Prometheus / Loki へ
振り分ける(``ops/`` の docker compose 一式を参照)。

属性は ``opt.*`` を最適化ドメインの semantic conventions として使う
(``opt.run_id`` / ``opt.model`` / ``opt.campaign_id`` / ``opt.axis.*`` /
``opt.gap`` / ``opt.status`` / ``opt.verdict.*``)。

過去タイムスタンプの送信になるため、Prometheus 側は out-of-order ingestion
(``storage.tsdb.out_of_order_time_window``)が必要(ops/ の設定は対応済み)。
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

try:
    from opentelemetry import trace as trace_api
    from opentelemetry._logs import LogRecord
    from opentelemetry._logs.severity import SeverityNumber
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
    from opentelemetry.sdk.metrics.export import (Gauge, Metric, MetricsData,
                                                  NumberDataPoint, ResourceMetrics,
                                                  ScopeMetrics)
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.util.instrumentation import InstrumentationScope
    from opentelemetry.trace import Status, StatusCode
except ModuleNotFoundError as _e:  # pragma: no cover - extras 未導入時の案内
    raise ModuleNotFoundError(
        "minlpkit.otel には OpenTelemetry SDK が必要です。"
        '`uv add "minlpkit[otel]"` で導入してください。'
    ) from _e

DEFAULT_ENDPOINT = "http://localhost:4318"
_SCOPE = InstrumentationScope("minlpkit", None)

# 診断 severity → OTel ログ severity の写像(提案は他テレメトリと同じレールに乗せる)
_SEVERITY = {
    "good": (SeverityNumber.INFO, "INFO"),
    "warning": (SeverityNumber.WARN, "WARN"),
    "serious": (SeverityNumber.ERROR, "ERROR"),
    "critical": (SeverityNumber.FATAL, "FATAL"),
}


def _ns(iso: str) -> int:
    """ISO文字列(ローカル時刻)→ epoch ナノ秒。"""
    return int(datetime.fromisoformat(iso).timestamp() * 1e9)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _clean_attrs(d: dict) -> dict:
    """OTel 属性に載せられる形に整える(None を除去、複合値は文字列化)。"""
    out = {}
    for k, v in d.items():
        if v is None:
            continue
        out[k] = v if isinstance(v, (bool, int, float, str)) else json.dumps(v, ensure_ascii=False)
    return out


class _Exporters:
    """3シグナル分のエクスポータ束。テストでは in-memory 実装を注入できる。"""

    def __init__(self, endpoint: str | None = None, *,
                 span_exporter=None, metric_exporter=None, log_exporter=None):
        ep = (endpoint or DEFAULT_ENDPOINT).rstrip("/")
        self.span = span_exporter or OTLPSpanExporter(endpoint=f"{ep}/v1/traces")
        self.metric = metric_exporter or OTLPMetricExporter(endpoint=f"{ep}/v1/metrics")
        self.log = log_exporter or OTLPLogExporter(endpoint=f"{ep}/v1/logs")


def _resource(model: str | None) -> "Resource":
    attrs = {"service.name": "minlpkit"}
    if model:
        attrs["opt.model"] = model
    return Resource.create(attrs)


def _emit_metrics(exporters: _Exporters, resource: "Resource", events: list[dict],
                  t0_ns: int, attrs: dict) -> int:
    """探索イベント列をゲージ(実時刻付き data point)として送る。

    SDK の Meter API は送信時刻を自動採番するため過去時刻を載せられない。
    ここでは MetricsData を直接組み立てて exporter へ渡す(公式データモデル準拠)。
    """
    series: dict[str, list[NumberDataPoint]] = {"gap": [], "primal": [], "dual": [], "nodes": []}
    for ev in events:
        ts = t0_ns + int(float(ev.get("time", 0.0)) * 1e9)
        for key in series:
            v = ev.get(key)
            if v is None:
                continue
            series[key].append(NumberDataPoint(
                attributes=attrs, start_time_unix_nano=t0_ns, time_unix_nano=ts,
                value=float(v) if key != "nodes" else int(v)))
    metrics = [Metric(name=f"opt.{k}", description=f"solver {k}", unit="1",
                      data=Gauge(data_points=pts))
               for k, pts in series.items() if pts]
    if not metrics:
        return 0
    data = MetricsData(resource_metrics=[ResourceMetrics(
        resource=resource,
        scope_metrics=[ScopeMetrics(scope=_SCOPE, metrics=metrics, schema_url="")],
        schema_url="")])
    exporters.metric.export(data)
    return sum(len(m.data.data_points) for m in metrics)


def _emit_log(logger, *, body: str, severity: str, ts_ns: int, attrs: dict,
              span=None) -> None:
    """1件のログレコードを送る(span を渡すと trace/log が相関する)。"""
    num, text = _SEVERITY.get(severity, (SeverityNumber.INFO, "INFO"))
    ctx = span.get_span_context() if span is not None else None
    logger.emit(LogRecord(
        timestamp=ts_ns, observed_timestamp=ts_ns,
        trace_id=ctx.trace_id if ctx else 0, span_id=ctx.span_id if ctx else 0,
        trace_flags=ctx.trace_flags if ctx else None,
        severity_text=text, severity_number=num,
        body=body, attributes=_clean_attrs(attrs)))


def export_run(run_dir: str | Path, *, endpoint: str | None = None,
               _exporters: _Exporters | None = None, _parent_span=None,
               _providers: tuple | None = None) -> dict:
    """記録済み run 1件を OTLP(trace + metrics + logs)へ送る。

    Args:
        run_dir: ``results/runs/<run_id>`` のパス。
        endpoint: OTLP HTTP エンドポイント(既定 ``http://localhost:4318``。
            Alloy の OTLP 受口)。

    Note:
        ``_exporters`` / ``_parent_span`` / ``_providers`` は内部用
        (`export_campaign` からの親スパン連結・テストでのエクスポータ注入)。

    Returns:
        dict: ``{"run_id", "trace_id", "n_events", "n_metric_points"}``。

    Raises:
        FileNotFoundError: ``meta.json`` が無い場合。
    """
    run_dir = Path(run_dir)
    meta = _read_json(run_dir / "meta.json")
    if meta is None:
        raise FileNotFoundError(f"meta.json が見つかりません: {run_dir}")
    summary = _read_json(run_dir / "summary.json") or {}
    events: list[dict] = []
    ev_path = run_dir / "events.jsonl"
    if ev_path.exists():
        for line in ev_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    run_id = meta.get("run_id", run_dir.name)
    model = meta.get("model")
    campaign = meta.get("campaign") or {}
    resource = _resource(model)
    own_providers = _providers is None
    if own_providers:
        exporters = _exporters or _Exporters(endpoint)
        tracer_provider = TracerProvider(resource=resource)
        tracer_provider.add_span_processor(SimpleSpanProcessor(exporters.span))
        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(SimpleLogRecordProcessor(exporters.log))
    else:
        exporters, tracer_provider, logger_provider = _providers

    t0_ns = _ns(meta.get("created", datetime.now().isoformat(timespec="seconds")))
    solve_time = summary.get("time")
    end_ns = (_ns(summary["finished"]) if "finished" in summary
              else t0_ns + int(float(solve_time or 0.0) * 1e9))
    if end_ns <= t0_ns:  # created が秒精度のため高速 run で逆転しうる
        end_ns = t0_ns + max(1, int(float(solve_time or 0.0) * 1e9))

    base_attrs = _clean_attrs({
        "opt.run_id": run_id, "opt.model": model,
        "opt.campaign_id": campaign.get("id"), "opt.campaign_kind": campaign.get("kind"),
        **{f"opt.axis.{k}": v for k, v in (campaign.get("axis") or {}).items()},
    })
    span_attrs = {**base_attrs, **_clean_attrs({
        "opt.status": summary.get("status"), "opt.gap": summary.get("gap"),
        "opt.objective": summary.get("objective"), "opt.nodes": summary.get("nodes"),
        "opt.time": solve_time, "opt.nsols": summary.get("nsols"),
        "opt.git_sha": (meta.get("capture") or {}).get("git_sha"),
    })}

    tracer = tracer_provider.get_tracer("minlpkit")
    parent_ctx = (trace_api.set_span_in_context(_parent_span)
                  if _parent_span is not None else None)
    span = tracer.start_span(f"solve {model or run_id}", context=parent_ctx,
                             start_time=t0_ns, attributes=span_attrs)
    for ev in events:
        if ev.get("event") == "incumbent":
            span.add_event("incumbent", attributes=_clean_attrs(
                {"opt.primal": ev.get("primal"), "opt.gap": ev.get("gap"),
                 "opt.nodes": ev.get("nodes")}),
                timestamp=t0_ns + int(float(ev.get("time", 0.0)) * 1e9))
    status = str(summary.get("status", ""))
    span.set_status(Status(StatusCode.ERROR, f"solver status: {status}")
                    if status == "infeasible" else Status(StatusCode.OK))
    span.end(end_time=end_ns)

    n_points = _emit_metrics(exporters, resource, events, t0_ns, base_attrs)

    logger = logger_provider.get_logger("minlpkit")
    gap = summary.get("gap")
    _emit_log(
        logger, span=span,
        body=f"run {run_id} finished: status={status}"
             f"{f', gap={gap * 100:.2f}%' if gap is not None else ''}",
        severity="critical" if status == "infeasible" else "good",
        ts_ns=end_ns, attrs={**span_attrs, "opt.event": "run_finished"})

    if own_providers:
        tracer_provider.shutdown()
        logger_provider.shutdown()
        exporters.metric.force_flush()
    ctx = span.get_span_context()
    return {"run_id": run_id, "trace_id": format(ctx.trace_id, "032x"),
            "n_events": len(events), "n_metric_points": n_points}


def export_campaign(campaign_dir: str | Path, *, runs_root: str | Path | None = None,
                    endpoint: str | None = None,
                    _exporters: _Exporters | None = None) -> dict:
    """campaign 一式(親スパン + 各 run + verdicts ログ)を OTLP へ送る。

    campaign は親スパン、各メンバー run は子スパンとして1本のトレースに束ね、
    verdicts(ライブラリからの提案)は severity 付きログとして送る(Grafana では
    Loki の Suggestions パネルと Tempo のトレースビューの両方から見える)。

    Args:
        campaign_dir: ``results/campaigns/<campaign_id>`` のパス。
        runs_root: メンバー run を探すルート(既定: ``campaign_dir/../../runs``)。
        endpoint: OTLP HTTP エンドポイント(既定 ``http://localhost:4318``)。
        _exporters: テスト用のエクスポータ注入。

    Returns:
        dict: ``{"campaign_id", "trace_id", "runs": [export_runの結果...],
        "n_verdicts"}``。

    Raises:
        FileNotFoundError: ``campaign.json`` が無い場合。
    """
    campaign_dir = Path(campaign_dir)
    c = _read_json(campaign_dir / "campaign.json")
    if c is None:
        raise FileNotFoundError(f"campaign.json が見つかりません: {campaign_dir}")
    runs_root = (Path(runs_root) if runs_root is not None
                 else campaign_dir.parent.parent / "runs")

    cid = c.get("campaign_id", campaign_dir.name)
    resource = _resource(c.get("name"))
    exporters = _exporters or _Exporters(endpoint)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporters.span))
    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(SimpleLogRecordProcessor(exporters.log))
    providers = (exporters, tracer_provider, logger_provider)

    # 親スパンの期間 = 各メンバー run の期間の包絡
    members = c.get("members", [])
    metas = [( _read_json(runs_root / mem["run_id"] / "meta.json") or {},
               _read_json(runs_root / mem["run_id"] / "summary.json") or {})
             for mem in members]
    starts = [_ns(m["created"]) for m, _ in metas if "created" in m]
    ends = [_ns(s["finished"]) for _, s in metas if "finished" in s]
    t0_ns = min(starts) if starts else _ns(c.get("created", datetime.now().isoformat()))
    t1_ns = max([*ends, t0_ns + 1])

    tracer = tracer_provider.get_tracer("minlpkit")
    parent = tracer.start_span(
        f"campaign {c.get('name', cid)} ({c.get('kind')})", start_time=t0_ns,
        attributes=_clean_attrs({
            "opt.campaign_id": cid, "opt.campaign_kind": c.get("kind"),
            "opt.model": c.get("name"), "opt.n_members": len(members),
            "opt.n_verdicts": len(c.get("verdicts", []))}))

    results = []
    for mem in members:
        run_dir = runs_root / mem["run_id"]
        if (run_dir / "meta.json").exists():
            results.append(export_run(run_dir, _parent_span=parent, _providers=providers))

    # verdicts(提案)は severity 付きログとして campaign トレースに相関させて送る
    logger = logger_provider.get_logger("minlpkit")
    verdicts = c.get("verdicts", [])
    for v in verdicts:
        _emit_log(
            logger, span=parent, body=v.get("verdict", ""),
            severity=v.get("severity", "warning"), ts_ns=t1_ns,
            attrs={"opt.campaign_id": cid, "opt.campaign_kind": c.get("kind"),
                   "opt.model": c.get("name"), "opt.group": v.get("group"),
                   "opt.evidence": v.get("evidence"), "opt.recipe": v.get("recipe"),
                   "opt.event": "verdict"})
    parent.set_status(Status(StatusCode.OK))
    parent.end(end_time=t1_ns)

    tracer_provider.shutdown()
    logger_provider.shutdown()
    exporters.metric.force_flush()
    ctx = parent.get_span_context()
    return {"campaign_id": cid, "trace_id": format(ctx.trace_id, "032x"),
            "runs": results, "n_verdicts": len(verdicts)}
