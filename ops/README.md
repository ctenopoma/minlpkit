# ops/ — minlpkit OpsOps スタック(Alloy + Tempo + Loki + Prometheus + Grafana)

最適化 run のテレメトリ(trace / metrics / logs)を OpenTelemetry(OTLP)で集め、
Grafana で横断監視するためのローカルスタック。アプリ側(`minlpkit.otel`)は
**Alloy の OTLP 受口に投げるだけ**で、バックエンドの振り分けは `alloy/config.alloy` が担う
(バックエンド差し替え時もアプリ無変更)。

```
minlpkit.otel ──OTLP(4318)──> Alloy ──┬─ traces  → Tempo      ┐
                                      ├─ logs    → Loki       ├─→ Grafana (3000)
                                      └─ metrics → Prometheus ┘
```

## 使い方

```bash
# 1. スタック起動
docker compose -f ops/docker-compose.yml up -d

# 2. campaign を実行して OTLP へ送る(--otel を付けるだけ)
uv run python experiments/run_campaign.py --kind ablate --time 15 --otel http://localhost:4318

# 2'. 記録済みの run / campaign を後からまとめて送ることもできる
uv run python -c "from minlpkit.otel import export_campaign; \
  export_campaign('results/campaigns/<campaign_id>')"

# 3. Grafana で閲覧(匿名Adminでログイン不要)
#    http://localhost:3000 → Dashboards → minlpkit → minlpkit OpsOps
```

## 3シグナルへの写像(最適化 semantic conventions)

| シグナル | 内容 | 属性(`opt.*`) |
| --- | --- | --- |
| Trace(Tempo) | campaign=親スパン、各run=子スパン、incumbent更新=スパンイベント | `opt.run_id` / `opt.campaign_id` / `opt.axis.*` / `opt.status` / `opt.gap` |
| Metrics(Prometheus) | `opt_gap` / `opt_primal` / `opt_dual` / `opt_nodes`(探索イベントの実時刻) | ラベル化: `opt_run_id` / `opt_campaign_id` / `opt_axis_off` など |
| Logs(Loki) | run完了サマリ + **verdicts(ライブラリからの提案)** を severity 付きで | `opt_event=verdict` / `opt_group` / `opt_recipe`、trace_id で Tempo と相関 |

診断 severity → OTel severity: good→INFO / warning→WARN / serious→ERROR / critical→FATAL。

## 注意(実測に基づく)

- **メトリクスは「求解直後の送信」でのみ完全**。Alloy の `otelcol.exporter.prometheus` は
  数分より古いデータポイントを stale として黙って落とすため、古い run のバックフィルでは
  trace / logs だけが入る(campaign 実行時に `--otel` を付ける運用が正)。
  Prometheus 側の `out_of_order_time_window: 30d` は分オーダーの遅延を救うための設定。
- **古いログ(>3時間)は Loki のチャンク flush までクエリに出ない**(querier が ingester に
  問い合わせるのは既定3時間以内のため)。すぐ見たいときは `curl -X POST localhost:3100/flush`。
  受入れ自体の上限は約1週間。
- メトリクス名にサフィックスが付かないよう `add_metric_suffixes = false` を設定済み
  (既定では unit "1" のゲージが `opt_gap_ratio` になる)。
- Grafana は実験用に匿名 Admin(`GF_AUTH_ANONYMOUS_*`)。公開環境ではそのまま使わないこと。
- 破棄: `docker compose -f ops/docker-compose.yml down -v`
