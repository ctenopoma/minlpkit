# Phase 16 精緻化バッチ3 — 結果記録

対象: 薄いサンプル10本(docstring精緻化 + モデルのリアリズム底上げ)。
各ファイルに `SCALES`(small/default/large)を導入し、`build_model(scale="default")` を既定挙動とした。
以下の変数数・制約数は `build_model("default")` を構築し `m.optimize()` 実行後に
`len(m.getVars())` / `len(m.getConss())` で取得した値(SCIPの前処理後の値を含む)。
「変更前」は元の `build_model()`(引数なし、固定サイズ)の変数・制約数。

| # | ファイル | 変更前 vars/cons | 変更後 vars/cons (default) | 新docstring要約 | 動作確認 |
|---|---|---|---|---|---|
| 1 | samples/energy_and_microgrid/hydro_thermal_coordination.py | 6 / 4 | 60 / 58 | 給電司令が火力ユニットの起動停止(整数)と水力の水資源制約を跨いだ多時間帯協調運転計画を決める | small/default/large 全て optimal |
| 2 | samples/scheduling/job_shop_flexible.py | 4 / 2 | 271 / 248 | 生産管理者がジョブ×工程の機械選択(整数)と離接制約による順序付けでメイクスパンを最小化する | small/default/large 全て optimal |
| 3 | samples/routing_and_logistics/last_mile_delivery.py | 6 / 6 | 48 / 80 | 配車担当者がMTZ制約付き容量制約下で1台の車両の巡回順序を最小コストで決める | small/default/large 全て optimal(容量400に調整し実行可能性を確保) |
| 4 | samples/finance_and_pricing/loan_portfolio_optimization.py | 3 / 2 | 40 / 20 | 与信管理者が複数商品×四半期の新規貸出配分をリスク上限・集中度上限のもとで期待利回り最大化する | small/default/large 全て optimal |
| 5 | samples/routing_and_logistics/maritime_inventory_routing.py | 10 / 5 | 54 / 39 | 船舶運航計画者が港ごとの在庫バランスと同時配船隻数(整数)の上限のもとで配船計画を決める | small/default/large 全て optimal |
| 6 | samples/others/media_mix_advertising.py | 3 / 1 | 60 / 13 | メディアプランナーが区分線形の飽和効果とメディア出稿オンオフ(整数)を考慮した予算配分を決める | small/default/large 全て optimal |
| 7 | samples/energy_and_microgrid/microgrid_islanded.py | 6 / 3 | 105 / 80 | 孤立地域の運転オペレーターが発電機起動停止(整数)・蓄電池充放電・負荷遮断を組み合わせた需給計画を決める | small/default/large 全て optimal |
| 8 | samples/packing_and_cutting/molded_parts_cutting.py | 3 / 1 | 80 / 28 | 生産計画者が金型切替(整数)と在庫バランスのトレードオフで段取り替えコストを最小化する | small/default/large 全て optimal(機械ロット上限を部品数に比例させ実行可能性を確保) |
| 9 | samples/routing_and_logistics/multi_echelon_distribution.py | 2 / 2 | 18 / 11 | サプライチェーン計画者が倉庫稼働の二値決定(整数)と3段階容量制約のもとでネットワーク費用を最小化する | small/default/large 全て optimal |
| 10 | samples/finance_and_pricing/portfolio_cvar.py | 3 / 1 | 26 / 22 | 資産運用担当者がRockafellar-Uryasev線形化によるCVaR制約のもとで期待リターンを最大化する | small/default/large 全て optimal(CVaR上限を0.22に調整し実行可能性を確保) |

## 修正メモ
- `last_mile_delivery.py`: 単一車両のMTZ定式化では車両容量が全顧客需要合計を上回る必要があるため、
  `VEHICLE_CAP` を100→400に引き上げて全scaleで実行可能にした。
- `molded_parts_cutting.py`: 機械の1期あたりロット数上限を固定値6のままにすると default/large scale で
  需要合計に対して生産能力が不足し infeasible になったため、`LOT_CAP_PER_PART * n_part` で部品数に
  比例するよう変更した。
- `portfolio_cvar.py`: `CVAR_LIMIT=0.12` では default scale のシナリオ集合でテールリスクが上限を
  超過し infeasible になったため、0.22 に緩和した。

## 検証
- 10本すべて `build_model("small"/"default"/"large")` → `m.optimize()` で `status == "optimal"` を確認
  (`limits/time=30` 秒でも全て時間内に最適解到達)。
- `uv run pytest -q` 実行結果は本ファイル末尾のコミットログ・Actions結果を参照。
