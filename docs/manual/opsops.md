# campaign と OpsOps(OpenTelemetry / Grafana 連携)

最適化の実務でよくある3つの反復作業を、minlpkit は **campaign**(軸を1つだけ変えた run 群)
という1つの抽象で自動化する:

| やりたいこと | 変える軸 | API |
| --- | --- | --- |
| 入力シナリオ(ファイル)を切り替えて一括求解 | 入力インスタンス | `mk.scenario_sweep` |
| SCIP パラメータを調整 | パラメータ | `mk.sweep`(既存) |
| 収束しない/実行不可能の犯人探し(制約を1個ずつ On/Off) | 制約グループ | `mk.ablate` |

各メンバーは通常の run として `results/runs/` に記録され、campaign 全体の要約と
**verdicts(ライブラリからの提案)** が `results/campaigns/<id>/campaign.json` に出る。

## 制約アブレーション(犯人探し)

```python
import minlpkit as mk

# groups: {グループ名: 制約名の接頭辞 or 述語}。省略すると制約名の接頭辞から自動抽出
df = mk.ablate(build_model, {
    "demand": "demand_",
    "kinetics": lambda name: name.startswith(("arrhenius_", "conversion_")),
}, name="plant", time_limit=15)
print(df[["axis", "status", "final_gap", "verdict"]])
```

baseline(全制約 On)と各グループ Off の run を比較し、次の verdict を自動で付ける:

- baseline が infeasible → Off で可解になった群は **実行不可能性に関与**(critical)。
  厳密な矛盾核は `mk.diagnose_infeasibility` で特定する
- baseline の gap が残る → Off で gap がほぼ閉じた群は **収束ボトルネック**(serious)。
  その群の緩和強化(線形化・境界タイト化)が効く
- Off で求解時間が 1/3 以下になった群は **求解時間の支配要因**(warning)

## 入力シナリオスイープ

```python
df = mk.scenario_sweep(lambda sc: build_model(demand_scale=sc),
                       {"low": 0.6, "base": 1.0, "peak": 2.0}, name="plant")
```

infeasible なシナリオ(critical)と、制限時間内に gap が閉じない難例(warning)に
verdict が付く。

## 閲覧(ローカル)

```bash
uv run python -m minlpkit.live.server
```

http://127.0.0.1:5000/campaigns に campaign 横断ビュー(マトリクス + 提案パネル)が出る。
行クリックで各 run のライブモニタへ遷移する。

## OpsOps: OpenTelemetry / Grafana 連携

継続運用(毎日のシナリオ一括求解、性能リグレッション監視)には、run / campaign を
OpenTelemetry(OTLP)で **Grafana Alloy → Tempo / Loki / Prometheus → Grafana** に流す。

```bash
uv add "minlpkit[otel]"                       # extras 導入
docker compose -f ops/docker-compose.yml up -d  # スタック起動(リポジトリの ops/ 参照)
uv run python experiments/run_campaign.py --kind ablate --otel http://localhost:4318
# → http://localhost:3000 (Grafana) → Dashboards → minlpkit OpsOps
```

3シグナルへの写像:

- **Trace(Tempo)**: campaign = 親スパン、各 run = 子スパン、incumbent 更新 = スパンイベント
- **Metrics(Prometheus)**: `opt_gap` / `opt_primal` / `opt_dual` / `opt_nodes`
  (探索イベントの実時刻でバックフィル)
- **Logs(Loki)**: run 完了サマリと verdicts(提案)を severity 付きで。trace_id で Tempo と相関

記録済みの run を後から送るには `minlpkit.otel.export_run` / `export_campaign` を使う。

!!! note "メトリクスは求解直後の送信でのみ完全"
    Alloy のメトリクス変換(`otelcol.exporter.prometheus`)は数分より古いデータポイントを
    stale として黙って落とすため、**古い run を後からバックフィルすると入るのは trace / logs のみ**。
    campaign 実行時に `--otel` を付けて求解直後に送るのが正しい運用。分オーダーの遅延は
    Prometheus 側の `storage.tsdb.out_of_order_time_window`(`ops/` は設定済み)が吸収する。
    また3時間より古いログは Loki のチャンク flush(`POST /flush` で強制可)までクエリに出ない。
