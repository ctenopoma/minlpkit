# Phase 16 バッチ1: 薄いサンプル精緻化 記録

対象: `task.md` Phase 16 バッチ1(10本)。docstringを事業ストーリー形式に書き換え、
2-4変数の純LPトイを「複数期/複数拠点/整数決定」等を足した軽量な現実的モデルへ拡張した。

## 一覧

| ファイル | 変更前 (vars/conss) | 変更後 (vars/conss) | 新docstring要約 | 動作確認 |
| --- | --- | --- | --- | --- |
| `manufacturing_and_blending/agribusiness_crop_mix.py` | 2 / 2 | 15 / 15 | 農業法人が5作物×2圃場の作付面積を、圃場面積・水・労働力制約と作付ロット下限(二値)・作物多様化下限のもとで最適化 | optimal, obj=211486.36 |
| `scheduling/airline_overbooking.py` | 1 / 0 | 15 / 12 | 航空会社が3便×2運賃クラスの予約受入数と保守的/積極的オーバーブッキング方針(二値)を、期待搭乗者数の座席容量制約のもとで最適化 | optimal, obj=120429.98 |
| `scheduling/airport_gate_assignment.py` | 4 / 4 | 26 / 18 | 空港が6便を4ゲート(ワイドボディ対応可否・時間帯排他)またはリモートスポットへ割当て、乗客満足度を最大化 | optimal, obj=576.00 |
| `scheduling/assembly_line_balancing_2.py` | 7 / 5 | 25 / 18 | 製造ラインが8タスクを先行関係付きで3ステーションに割当て、サイクルタイム(Type-II ALB)を最小化 | optimal, obj=12.00 |
| `manufacturing_and_blending/automotive_paint_shop.py` | 3 / 1 | 23 / 24 | 塗装工程が6スロット×3色の生産順序を色替え検知(startup型二値)付きで決め、需要充足のもとで段取りコストを最小化 | optimal, obj=100.00 |
| `manufacturing_and_blending/beverage_bottling_line.py` | 6 / 1 | 20 / 21 | ボトリングラインが3SKU×3シフトの稼働(二値)・生産量(連続)を、切替検知と需要充足のもとで段取りコスト最小化 | optimal, obj=600.00 |
| `others/bike_sharing_rebalancing.py` | 2 / 1 | 24 / 16 | シェアサイクル運営が4ステーション間の自転車再配置(整数移動量+出動二値)を、需給フロー保存則のもとで最小コスト化 | optimal, obj=255.00 |
| `scheduling/bus_driver_rostering.py` | 6 / 4 | 35 / 17 | バス営業所が5運転士×週7日の勤務表を、曜日別必要人数・最大勤務日数・週休下限のもとで人件費最小化 | optimal, obj=3600.00 |
| `scheduling/cement_mill_scheduling.py` | 6 / 3 | 22 / 15 | セメント工場が2ミル×6時間帯の稼働(二値)を、ピーク時間帯停止・起動検知・日次生産量下限のもとで運転コスト最小化 | optimal, obj=93.00 |
| `finance_and_pricing/credit_scoring_tree.py` | 1 / 1 | 12 / 22 | 消費者金融が2セグメント(若年/シニア)別スコアカットオフ(連続)と申込者ごとの承認可否(二値、big-M連携)を、謝絶率上限のもとで期待損益最大化 | optimal, obj=890.00 |

## 補足

- `airline_overbooking`: 当初「二値 × 連続」の積(オーバーブッキング方針コスト率 × 期待搭乗者数)を
  そのまま目的関数に書いたため SCIP の `setObjective` が非線形を拒否した
  (`ValueError: SCIP does not support nonlinear objective functions`)。
  補助変数 `bump[f]` を導入し、big-M による2本の下限制約(方針ごとの単価)で線形化して解消。
- `automotive_paint_shop` / `beverage_bottling_line`: 当初は「各色/各SKUを専用スロットに
  ロットまとめ」した場合に必要なスロット数(需要 ÷ スロット能力の切り上げ合計)が
  利用可能スロット数を上回り infeasible だった。スロット数・シフト容量を需要と整合する値に調整して解消
  (paint_shop: `N_SLOTS` 5→6、bottling_line: `SHIFT_CAPACITY` 4000→6500)。
- 上記以外の7本は初回の実装でそのまま optimal に到達。

## 検証

- 10本すべて `import` → `build_model()` → `optimize()` が個別に成功し、`status == "optimal"` を確認
  (上表参照、コマンド例は各ファイル冒頭に相当する `uv run python -c "..."` ワンライナー)。
- `uv run pytest -q`: 53 passed, 2 skipped(既存テストへの影響なし)。
