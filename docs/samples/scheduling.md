# スケジューリング

ジョブショップ・シフト・保守・列車運行など時間軸の割当計画。本リポジトリ最大のカテゴリで、対称性や時間結合の題材が揃う。

**21 本** / `scale` 引数対応 1 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| airline_overbooking | 航空便オーバーブッキング・収益管理 (Airline Overbooking Control) — 航空会社の収益管理(レベニューマネジメント)部門が、複数便・複数運賃クラス(ビジネス/ | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/airline_overbooking.py) |
| airport_gate_assignment | 空港フライト・ゲート自動割当 (Airport Gate Assignment) — 空港の地上運航管理者(グランドオペレーション)が、当日の到着便をどのゲートに割り当てるかを | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/airport_gate_assignment.py) |
| assembly_line | Assembly Line Balancing Problem — This model assigns tasks to workstations such that precedence constraints are respected | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/assembly_line.py) |
| assembly_line_balancing_2 | アセンブリラインバランシング Type-II (Assembly Line Balancing) — 製造ラインの工程設計担当者(インダストリアルエンジニア)が、既に決まっているステーション数 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/assembly_line_balancing_2.py) |
| battery_train_scheduling | 蓄電池列車(BEMU)の運行ダイヤ・充電スケジュール統合最適化 (MILP) — 電化区間と非電化区間が混在する路線において、蓄電池搭載型列車 (BEMU) の | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/battery_train_scheduling.py) |
| bus_driver_rostering | バス運転士勤務表自動生成 (Bus Driver Rostering) — バス営業所の運行管理者が、1週間分の運転士シフトを決める。曜日ごとに必要な出勤人数 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/bus_driver_rostering.py) |
| cement_mill_scheduling | セメントミル操業スケジュール (Cement Mill Scheduling) — セメント工場のエネルギー管理担当者が、2基あるミル(粉砕設備)の稼働スケジュールを | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/cement_mill_scheduling.py) |
| hydro_scheduling | Pumped-Storage Hydroelectric Scheduling — This model schedules pumping and generating for a pumped-storage hydroelectric plant to… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/hydro_scheduling.py) |
| job_shop | Job Shop Scheduling Problem. — This model schedules a set of multi-operation jobs on a set of machines | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/job_shop.py) |
| job_shop_flexible | フレキシブルジョブショップスケジューリング (Flexible Job Shop). — 生産管理者が、複数のジョブ(受注ロット)を複数の工程(オペレーション)からなる | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/job_shop_flexible.py) |
| maintenance_production_scheduling | 予防保全と生産の同時スケジューリング (Simultaneous Production and Maintenance Scheduling) — 工場内の複数の製造ラインにおいて、製品の生産計画（ジョブ割り当て）と、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/maintenance_production_scheduling.py) |
| power_aware_scheduling | 電力価格連動型の生産スケジューリング (Power-Aware Production Scheduling) — 時間帯ごとに大きく変動する電力価格（リアルタイムプライシング）を考慮し、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/power_aware_scheduling.py) |
| rcpsp | Resource-Constrained Project Scheduling Problem (RCPSP). — This model schedules a set of project tasks under precedence and resour… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/rcpsp.py) |
| sequence_dependent_flowshop | 順序依存の段取り時間を考慮したフローショップスケジューリング問題 (SDST Flowshop) — 複数種類の製品（ジョブ）を複数の連続する工程（マシン）で処理するフローショップにおいて、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/sequence_dependent_flowshop.py) |
| shift_scheduling | Shift Scheduling Problem. — This model schedules employees to shifts to meet varying demand across periods, | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/shift_scheduling.py) |
| sports_scheduling | Sports Scheduling Problem — This model formulates a single round-robin tournament scheduling problem. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/sports_scheduling.py) |
| stn_batch_scheduling | 化学プラントのバッチプロセススケジューリング (STNモデル) — State-Task Network (STN)モデルに基づき、原料から中間体を経て最終製品を生産する | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/stn_batch_scheduling.py) |
| traffic_light_sync | 信号制御同期化・渋滞緩和 (Traffic Light Synchronization) — 自治体の交通管制センターが、幹線道路沿いに並ぶ複数交差点の信号サイクルにおける | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/traffic_light_sync.py) |
| train_rescheduling_disruption | 列車運行の障害時再スケジュール (Rescheduling under Disruption) モデル (MILP) — 事故や災害などによる急なダイヤ乱れ（特定区間での速度制限、駅での出発遅延など）が発生した際に、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/train_rescheduling_disruption.py) |
| train_scheduling | 電車運行計画・列車ダイヤグラム最適化問題 (Train Timetable Scheduling) — 同一の鉄道路線（複数駅）を走行する複数の列車（急行列車と普通列車など）のダイヤグラム（運行時間表）を最適化します。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/train_scheduling.py) |
| unit_commitment | プラント系 Unit Commitment (MINLP) — ユニットON/OFF(バイナリ) + 出力(連続)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/scheduling/unit_commitment.py) |

[← カタログ全体へ戻る](index.md)
