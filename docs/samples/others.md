# その他(基礎・拡張題材)

スケジューリングの基礎版やプラント物理入り拡張など、可視化・診断のベースライン比較に使う題材。

**12 本** / `scale` 引数対応 3 本。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| bike_sharing_rebalancing | シェアサイクル再配置ルーティング (Bike Sharing Rebalancing) — シェアサイクル運営会社のオペレーションチームが、夜間にトラックで自転車を運び、朝の需要ピークに備えてステーション間の在庫を調整する再配置計画を立てる。通勤駅前ステーションは朝に不足しやすく、住宅街ステーションは余剰になりやすいという非対称な偏りを、最小コストの車両移動で解消したい。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/bike_sharing_rebalancing.py) |
| fixed_charge | 固定費付き生産計画 (MILP) — Big-M改善の実証用 — 各施設 i は開設(y_i=1)して初めて生産 x_i>0 できる。開設に固定費 f_i。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/fixed_charge.py) |
| fixed_charge_network | 固定費用付きネットワークフロー問題 (Fixed Charge Network Flow Problem) — 物流ネットワーク設計担当者が、複数の配送センター・中継拠点・最終拠点からなるネットワーク上で、どの輸送ルート(リンク)を開設し、それぞれにどれだけの物量を流すかを決める問題である。各リンクを使うと(トラック便の契約・専用線の敷設など)固定費用が発生し、さらに実際に運ぶ物量に比例した変動輸送費用もかかる。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/fixed_charge_network.py) |
| media_mix_advertising | 広告予算メディアミックス配分 (Media Mix Advertising). — マーケティング部門のメディアプランナーが、四半期の広告予算を複数のメディア | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/media_mix_advertising.py) |
| parallel_machines | 恒等並列機械へのジョブ割当 (MILP, 強い対称性を持つ) — 対称性検出・対称性除去の題材。機械が恒等なので任意の2機械を | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/parallel_machines.py) |
| railway_line_planning | 鉄道運行系統・線路容量計画 (Railway Line Planning) — 鉄道事業者の「運行計画部門」が、複数の運行系統(路線)についてダイヤ改正時の運行頻度(1時間あたりの本数)を決める意思決定である。各系統は速達型・各停型など列車種別(サービスクラス)によって停車パターン・所要時間・収益単価が異なり、駅間の共有区間では複数系統の列車本数の合計が線路容量(閉塞・信号システムが許す最大本数)を超えてはならない。また車両基地の保有編成数が運行に必要な編成数の上限を規定する。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/railway_line_planning.py) |
| scheduling | バッチスケジューリング (MINLP) — ジョブごとにバッチ数(整数)×バッチサイズ(連続)を決め、マシンに割り当てる。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/scheduling.py) |
| scheduling_plant | バッチ反応器スケジューリング + プラント物理モデル (MINLP) — scheduling.py の拡張版。バッチ処理を「反応器の物理挙動」で置き換え、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/scheduling_plant.py) |
| smart_home_appliances | スマートホーム家電個別制御スケジュール (Smart Home Appliances) — 家庭用エネルギーマネジメントシステム(HEMS)が、複数の家電(食洗機・洗濯機・EV充電器等)の稼働時間帯を、時間帯別電気料金が最も安くなるように自動決定する意思決定である。各家電は所定の連続稼働時間数を1日の中のどこかに割り当てる必要があり、家庭の契約ブレーカー容量(同時使用可能な最大消費電力)を各時間帯で超えてはならない。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/smart_home_appliances.py) |
| supply_contract_selection | 調達契約オプション選定 (Supply Contract Selection) — 調達部門のバイヤーが、複数のサプライヤーが提示する契約オプション(固定価格契約・ | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/supply_contract_selection.py) |
| telecom_5g_slicing | 5Gネットワークスライシングリソース割当 (5G Telecom Slicing) — 通信事業者のネットワークオペレーションセンターが、基地局ごとに限られた無線帯域を | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/telecom_5g_slicing.py) |
| urban_parking_allocation | 都市型スマート駐車場予約割当 (Urban Parking Allocation) — スマート駐車場アプリの運営者が、予約リクエストを出した複数の車両を複数の駐車場 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/others/urban_parking_allocation.py) |

[← カタログ全体へ戻る](index.md)
