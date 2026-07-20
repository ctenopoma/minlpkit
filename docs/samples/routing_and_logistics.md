# 経路・物流

配送・巡回・車両割当・在庫輸送。経路変数(離散)と非線形コストを含む物流モデル群。

**13 本** / `scale` 引数対応 5 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| cross_docking | クロスドッキング拠点のドア割当・仕分け計画 (Cross-docking Scheduling) — 3PL倉庫のクロスドック(在庫を持たず入荷トラックから出荷トラックへ即座に積み替える拠点)で、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/cross_docking.py) |
| hub_and_spoke | 物流ネットワークのハブ立地・スポーク割当計画 (Hub and Spoke Network Design) — 物流ネットワーク設計担当者が、複数の拠点候補の中からハブ(集約中継拠点)をいくつ・どこに | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/hub_and_spoke.py) |
| last_mile_delivery | ラストマイル配送ルート最適化 (Last-mile Delivery). — 配送センターの配車担当者が、当日の複数配送先を1台(または少数)の車両で | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/last_mile_delivery.py) |
| maritime_inventory_routing | 海運在庫配送計画問題 (Maritime Inventory Routing). — 船舶運航計画者が、複数の受入港(顧客拠点)の在庫水準を許容範囲内に保ちながら、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/maritime_inventory_routing.py) |
| multi_echelon_distribution | 多階層物流ネットワーク配送計画 (Multi-echelon Distribution). — サプライチェーン計画者が、工場から複数の中継倉庫を経て複数の顧客地域へ製品を | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/multi_echelon_distribution.py) |
| ride_hailing_matching | 配車サービス・ドライバーマッチング (Ride-hailing Matching) — 配車プラットフォームの「ディスパッチ担当」(自動マッチングエンジン)が、ある短い時間窓に | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/ride_hailing_matching.py) |
| supply_chain | Multi-echelon Supply Chain Network Design. — This model determines which plants and distribution centers to open | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain.py) |
| supply_chain_multi_commodity | 多品種サプライチェーン計画 (Multi-commodity Supply Chain Planning) — 複数拠点(工場・倉庫)を持つメーカーの「サプライチェーン計画担当」が、複数品目を | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain_multi_commodity.py) |
| supply_chain_multi_period | 多期間サプライチェーンネットワーク計画 (Multi-period Supply Chain Network Planning) — サプライチェーン計画担当者が、複数期間・複数拠点(工場→配送センター→顧客)にわたる | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain_multi_period.py) |
| tsp_sec | Traveling Salesman Problem (TSP) with Subtour Elimination Constraints. — This model implements the TSP using MTZ-like continuous v… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/tsp_sec.py) |
| vrp_mtz | Capacitated Vehicle Routing Problem (CVRP) using MTZ formulation. — This model implements the classic Miller-Tucker-Zemlin (MTZ) f… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/vrp_mtz.py) |
| vrp_tw | 時間枠付き配送計画問題 (Vehicle Routing with Time Windows) — 配送センターのルート計画担当者が、1台の車両が複数の顧客を巡回する順序と各顧客への | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/vrp_tw.py) |
| waste_collection_routing | ゴミ収集配送ルート最適化 (Waste Collection Routing) — 自治体の廃棄物収集事業者が、複数の収集拠点(集積所)を複数台の収集車でどう分担して | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/waste_collection_routing.py) |

[← カタログ全体へ戻る](index.md)
