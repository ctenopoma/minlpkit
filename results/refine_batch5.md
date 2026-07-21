# Phase 16 バッチ5: docstring精緻化 + モデルのリアリズム底上げ

対象11本(`samples/` 配下、担当ファイルのみ)。各ファイルについて、docstringを
「誰が・何を・なぜ決めるか+主要制約の業務的意味」の2-4文へ書き換え、2-4変数の
純LP(トイ)を業務的に自然な範囲で拡張(複数期/複数拠点/整数決定/disjunctive結合など)した。

## 結果一覧

| ファイル | 変数数(前→後) | 制約数(前→後) | 新docstring要約 | 動作確認 |
| --- | --- | --- | --- | --- |
| routing_and_logistics/supply_chain_multi_period.py | 8 → 36 | 4 → 24 | 拠点×期間の在庫バランス+トラック台数(整数)による輸送ロット制約 | optimal (gap 0%, Cost=2928.6) |
| others/supply_contract_selection.py | 2 → 9 | 1 → 8 | 契約ごとの固定費・最低発注量・上限を伴う0-1受諾判断+品目別発注量配分 | optimal (gap 0%, Cost=2420.0) |
| others/telecom_5g_slicing.py | 3 → 12 | 1 → 12 | スライス受諾(0-1)+最低保証帯域SLA×時間帯別帯域割当 | optimal (gap 0%, Revenue=6480.0) |
| scheduling/traffic_light_sync.py | 2 → 11 | 1 → 10 | 青時間配分+交差点間オフセットのグリーンウェーブ整合(big-M disjunctive) | optimal (gap 0%, Value=420.0) |
| location_and_network_design/transmission_expansion.py | 4 → 9 | 3 → 8 | 候補線建設(0-1)×複数需要期(平常/ピーク)の潮流同時決定 | optimal (gap 0%, Cost=2557.5) |
| others/urban_parking_allocation.py | 4 → 18 | 2 → 12 | 車両×駐車場の効用最大化割当+時間帯別容量制約 | optimal (gap 0%, Utility=84.0) |
| energy_and_microgrid/virtual_power_plant.py | 12 → 28 | 4 → 16 | ガスエンジンの起動(0-1)+最低出力維持、蓄電池SOC繰越、太陽光上限を含む複数DER集約入札 | optimal (gap 0%, Revenue=2049.0) |
| routing_and_logistics/vrp_tw.py | 3 → 10 | 4 → 12 | 訪問順序(0-1, big-M)×到着時刻の時間枠制約の同時最適化 | optimal (gap 0%, Total time=30.0) |
| packing_and_cutting/warehouse_slotting.py | 4 → 15 | 4 → 8 | SKU×スロットのピッキング効率最大化+スロット体積上限のナップサック制約(混載可) | optimal (gap 0%, Value=70.0) |
| routing_and_logistics/waste_collection_routing.py | 4 → 12 | 2 → 8 | 拠点×収集車の割当+車両積載重量容量制約 | optimal (gap 0%, Cost=61.0) |
| energy_and_microgrid/wind_battery_dispatch.py | 16 → 30 | 8 → 24 | 風力出力平準化のための充放電モード排他(0-1)+SOC時系列繰越(T=4→6) | optimal (gap 0%, Revenue=1587.0) |

## 動作確認方法

各ファイルを `uv run python <file>` で直接実行し、SCIPログの `Gap: 0.00 %` と
最終出力(目的関数値)を確認した(11本すべて optimal で終了)。

## 備考

- `tests/test_pipeline.py::test_analyze_airline_overbooking_no_constraints` が
  `uv run pytest -q` 全体実行で1件failしているが、対象は
  `samples/scheduling/airline_overbooking.py`(batch 1担当・並行編集中のファイル)であり、
  本バッチ(batch 5)の担当範囲外・本バッチの変更とは無関係(作業ツリーで当該ファイルが
  `M`状態で編集中であることを確認済み)。
- `transmission_expansion.py`(本バッチ対象・薄い版)と `transmission_expansion_operation.py`
  (T3旗艦)は別ファイルであり、後者は一切編集していない。
