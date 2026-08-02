# OTel export (otel)

Maps recorded runs / campaigns to OpenTelemetry (OTLP) traces / metrics / logs and ships
them (Grafana Alloy → Tempo / Loki / Prometheus; see the docker compose files under `ops/`).

Requires extras: `uv add "minlpkit[otel]"`.

::: minlpkit.otel
    options:
      members:
        - export_run
        - export_campaign
