# 経路・物流

配送・巡回・車両割当・在庫輸送。経路変数(離散)と非線形コストを含む物流モデル群。

**16 本** / `scale` 引数対応 8 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| cross_docking | クロスドッキング拠点のドア割当・仕分け計画 (Cross-docking Scheduling) — 3PL倉庫のクロスドック(在庫を持たず入荷トラックから出荷トラックへ即座に積み替える拠点)で、オペレーション担当者が「どの入荷トラックをどのドアで荷降ろしし、どの出荷トラックをどのドアで積込みするか」「入荷した各品目をどの出荷便へ何個ずつ仕分けるか」を同時に決める。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/cross_docking.py) |
| hub_and_spoke | 物流ネットワークのハブ立地・スポーク割当計画 (Hub and Spoke Network Design) — 物流ネットワーク設計担当者が、複数の拠点候補の中からハブ(集約中継拠点)をいくつ・どこに開設するかと、各拠点(スポーク)をどのハブに割り当てるかを同時に決める。ハブ拠点は集約効果でハブ間輸送コストが割安になる一方、開設固定費とハブ容量(処理能力)の制約があるため、拠点数(開設候補数の上限)と各拠点発の物量をどのハブ経由で流すかを合わせて最適化する必要がある(古典的な p-ハブ・メディアン問題の簡略版)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/hub_and_spoke.py) |
| last_mile_delivery | ラストマイル配送ルート最適化 (Last-mile Delivery). — 配送センターの配車担当者が、当日の複数配送先を1台(または少数)の車両で | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/last_mile_delivery.py) |
| maritime_inventory_routing | 海運在庫配送計画問題 (Maritime Inventory Routing). — 船舶運航計画者が、複数の受入港(顧客拠点)の在庫水準を許容範囲内に保ちながら、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/maritime_inventory_routing.py) |
| maritime_inventory_routing_realistic | 複数船舶の配船スケジューリング+港湾在庫統合計画 (Realistic Maritime Inventory Routing). — 海運会社の配船計画者が、異なる積載容量を持つ複数のタンカー(船隊)について、「どの船をいつどの港に配船するか(整数の配船スケジュール)」と「各港でどれだけ荷役するか(積載量、在庫制約付き)」を**同時に**決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/maritime_inventory_routing_realistic.py) |
| multi_echelon_distribution | 多階層物流ネットワーク配送計画 (Multi-echelon Distribution). — サプライチェーン計画者が、工場から複数の中継倉庫を経て複数の顧客地域へ製品を | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/multi_echelon_distribution.py) |
| multi_echelon_inventory_realistic | 多段階在庫計画(工場→DC→小売、リードタイム跨ぎ+安全在庫) (Realistic Multi-Echelon Inventory). — サプライチェーン計画者が、単一工場から複数の配送センター(DC)を経て複数の小売店へ商品を補充する3段階在庫網について、各段の発注量(整数ロット)・安全在庫の維持・欠品時の機会損失を週次で計画する意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/multi_echelon_inventory_realistic.py) |
| production_distribution_integrated | 生産-配送統合計画 (Integrated Production-Distribution / Lot-sizing + VRP-lite). — 複数工場を持つメーカーの「生産・物流統合計画者」が、各週(期)について(a) どの工場でいつ段取り(setup)して何を作るか(ロットサイジング)と(b) 作った製品をどの配送センター(DC)へ何台のトラックで運ぶか(車両割当)を**同時に**決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/production_distribution_integrated.py) |
| ride_hailing_matching | 配車サービス・ドライバーマッチング (Ride-hailing Matching) — 配車プラットフォームの「ディスパッチ担当」(自動マッチングエンジン)が、ある短い時間窓に発生した複数の配車リクエストに対して、稼働中の複数ドライバーをどう割り当てるかを決める意思決定である。各ドライバーは同時に1件までしか対応できず、各乗客も1台のみに割り当てられる(一対一マッチング)。マッチングの価値はドライバーと乗客の距離(迎車時間)・乗客の優先度(プレミアム会員か)によって変わる。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/ride_hailing_matching.py) |
| supply_chain | 多段階サプライチェーン網の設計 (Multi-echelon Supply Chain Network Design) — 消費財メーカーのサプライチェーン企画担当者が、工場と物流拠点(ディストリビューションセンター、DC)をどこに開設し、顧客への出荷までの物流網をどう組むかを決める。工場・DCにはそれぞれ開設すると固定費がかかり、稼働させる拠点数を絞ればコストは下がるが供給能力・輸送距離とのトレードオフが生じる。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain.py) |
| supply_chain_multi_commodity | 多品種サプライチェーン計画 (Multi-commodity Supply Chain Planning) — 複数拠点(工場・倉庫)を持つメーカーの「サプライチェーン計画担当」が、複数品目を複数の供給拠点から複数の需要拠点(顧客・DC)へどう配分するかを決める意思決定である。各供給拠点には品目ごとの生産・出荷能力があり、各需要拠点には品目ごとの最低充足すべき需要量がある。輸送には拠点間のリンクごとに単価が異なり、遠距離輸送ほどコストが高い。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain_multi_commodity.py) |
| supply_chain_multi_period | 多期間サプライチェーンネットワーク計画 (Multi-period Supply Chain Network Planning) — サプライチェーン計画担当者が、複数期間・複数拠点(工場→配送センター→顧客)にわたる | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/supply_chain_multi_period.py) |
| tsp_sec | 巡回セールスマン問題(部分巡回路除去付き) (Traveling Salesman Problem with Subtour Elimination Constraints) — 訪問営業担当者が、拠点(自社オフィス)から出発して全ての訪問先を1回ずつ回り、再び拠点に戻ってくる最短ルートを決める。訪問先同士の移動距離はあらかじめ分かっており、総移動距離を最小化する巡回順を求める必要がある。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/tsp_sec.py) |
| vrp_mtz | 容量制約付き配送計画問題 (Capacitated Vehicle Routing Problem, CVRP) - MTZ定式化 — 物流センターの配送計画担当者が、倉庫(デポ)から出発する複数台のトラックで、複数の顧客先に商品を届けるルートを決める。各トラックには積載容量の上限があり、1台で全顧客を回りきれない場合は複数台に配送先を分担させる必要がある。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/vrp_mtz.py) |
| vrp_tw | 時間枠付き配送計画問題 (Vehicle Routing with Time Windows) — 配送センターのルート計画担当者が、1台の車両が複数の顧客を巡回する順序と各顧客への | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/vrp_tw.py) |
| waste_collection_routing | ゴミ収集配送ルート最適化 (Waste Collection Routing) — 自治体の廃棄物収集事業者が、複数の収集拠点(集積所)を複数台の収集車でどう分担して | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/routing_and_logistics/waste_collection_routing.py) |

[← カタログ全体へ戻る](index.md)
