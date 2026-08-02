# OTelエクスポート (otel)

記録済みの run / campaign を OpenTelemetry(OTLP)の trace / metrics / logs へ写像して
送る(Grafana Alloy → Tempo / Loki / Prometheus。`ops/` の docker compose 一式を参照)。

追加依存(opentelemetry-sdk / otlp-http exporter)が必要。`uv add "minlpkit[otel]"` で導入する。

::: minlpkit.otel
    options:
      members:
        - export_run
        - export_campaign
