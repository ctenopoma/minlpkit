# その他(基礎・拡張題材)

スケジューリングの基礎版やプラント物理入り拡張など、可視化・診断のベースライン比較に使う題材。

**12 本** / `scale` 引数対応 0 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| bike_sharing_rebalancing | シェアサイクル再配置ルート (Bike Sharing Rebalancing) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/bike_sharing_rebalancing.py) |
| fixed_charge | 固定費付き生産計画 (MILP) — Big-M改善の実証用 — 各施設 i は開設(y_i=1)して初めて生産 x_i>0 できる。開設に固定費 f_i。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/fixed_charge.py) |
| fixed_charge_network | Fixed Charge Network Flow Problem. — This model minimizes the total cost of routing flow through a network, where | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/fixed_charge_network.py) |
| media_mix_advertising | 広告予算メディアミックス配分 (Media Mix Advertising) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/media_mix_advertising.py) |
| parallel_machines | 恒等並列機械へのジョブ割当 (MILP, 強い対称性を持つ) — 対称性検出・対称性除去(Phase 4)の題材。機械が恒等なので任意の2機械を | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/parallel_machines.py) |
| railway_line_planning | 鉄道運行系統・線路容量計画 (Railway Line Planning) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/railway_line_planning.py) |
| scheduling | バッチスケジューリング (MINLP) — ジョブごとにバッチ数(整数)×バッチサイズ(連続)を決め、マシンに割り当てる。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/scheduling.py) |
| scheduling_plant | バッチ反応器スケジューリング + プラント物理モデル (MINLP) — scheduling.py の拡張版。バッチ処理を「反応器の物理挙動」で置き換え、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/scheduling_plant.py) |
| smart_home_appliances | スマートホーム家電個別制御スケジュール (Smart Home Appliances) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/smart_home_appliances.py) |
| supply_contract_selection | 調達契約オプション選定 (Supply Contract Selection) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/supply_contract_selection.py) |
| telecom_5g_slicing | 5Gネットワークスライシングリソース割当 (5G Telecom Slicing) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/telecom_5g_slicing.py) |
| urban_parking_allocation | 都市型スマート駐車場予約割当 (Urban Parking Allocation) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/urban_parking_allocation.py) |

[← カタログ全体へ戻る](index.md)
