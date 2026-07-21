# 立地・ネットワーク設計

施設配置・送電/ガス/水素ネットワーク設計。開設(整数)×運用(連続)の統合意思決定で、ベンダーズ分解の適性を持つモデルを含む。

**14 本**(うち事業ストーリーが特に詳しいもの ⭐ 3 本) / `scale` 引数対応 3 本。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| ⭐ **gas_pipeline_weymouth** | ガス圧送ネットワークの運用計画 (Gas Pipeline Network with Weymouth Flow-Pressure). — 都市ガス/天然ガス輸送会社の「圧送運用部」が、1日(または数日)を通じて、供給拠点からの基本供給量、各コンプレッサ(圧送機)の起動/停止と昇圧量、そして緊急時の局所ピークシェイビング供給を決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/gas_pipeline_weymouth.py) |
| ⭐ **hydrogen_hub_transport** | 水素サプライチェーン: ハブ配置 + 多期輸送計画 (Hydrogen Hub Location & Transport). — 水素サプライチェーンを構築するエネルギー事業者の「計画担当者」が、候補地の中から「どこに生産・貯蔵ハブを開設し、どれだけの生産・貯蔵容量を持たせるか」(整数の開設可否 + 連続の容量)を決め、開設したハブから複数の需要地(水素ステーション等)へ「複数期にわたってどれだけ輸送するか」(連続)を同時に決める投資・運用意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/hydrogen_hub_transport.py) |
| ⭐ **transmission_expansion_operation** ([学習notebook](../notebooks/samples/transmission_expansion_operation.ipynb)) | 送電線増強計画 + 増強後運用の同時決定 (Transmission Expansion Planning with Operation). — 電力広域系統運用機関の「系統計画者」が、複数年に一度の投資計画サイクルで「どの候補送電線(コリドー)を新設・増強するか」(整数)を決め、その増強後の系統で「複数の需要シナリオそれぞれに対する給電運用(DC潮流)」(連続)を同時に検討する意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/transmission_expansion_operation.py) |
| battery_train_charger_location | 蓄電池列車(BEMU)のための駅急速充電設備 最適配置モデル (MILP) — 非電化区間を運行する蓄電池搭載型列車(BEMU)において、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/battery_train_charger_location.py) |
| district_heating_network_design_minlp | 地域熱供給網におけるプラント配置・パイプライン敷設・サイジング同時最適化 (MINLP) — 複数の需要家が存在する地域において、どこに熱源プラントを配置し、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/district_heating_network_design_minlp.py) |
| facility | 容量制約付き施設配置 (MILP, 純粋に線形) — 線形IIS・スラック(拘束制約)可視化の検証用モデル。非線形項を持たず、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/facility.py) |
| facility_location_capacitated | 容量制約付き複数期施設配置問題 (Capacitated Facility Location) — サプライチェーン計画担当者が、需要が季節的に変動する複数期間を見据えて、どの倉庫拠点を開設するか(整数の開設判断、一度開けば全期間使える固定資産)と、開設後の各期において各拠点からどの顧客へどれだけ供給するかを同時に決める。拠点の開設は一度きりの投資判断だが、容量制約と需要充足は期ごとに独立して効くため、需要が繁忙期に偏っている場合はピーク期の需要を満たせるだけの拠点網を用意しておく必要がある(時間結合)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/facility_location_capacitated.py) |
| gas_network_opt | 天然ガス配送網の圧力・バイパス投資計画 (Gas Network Optimization - MINLP) — ガス配送事業者のネットワーク計画担当者が、水源(コンプレッサ)から中継点を経て需要地へガスを送る直列パイプラインの運転圧力を、季節ごとの需要変動(2期)に対して決める。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/gas_network_opt.py) |
| hub_location | ハブ&スポーク型物流ネットワークのハブ配置問題 (Hub Location Problem) — 広域宅配便事業者のネットワーク設計担当者が、各拠点間で発生する荷物量(フロー)を踏まえて、どの拠点をハブ(集約・仕分け拠点)として開設するか、そして各スポーク拠点をどのハブに割り当てるかを同時に決める問題である。全拠点間を直接輸送すると輸送網が組合せ的に膨れ上がり非効率なので、荷物はいったんハブに集約してから別のハブを経由し、最後に宛先のスポーク拠点へ配送する「ハブ&スポーク」方式を取る。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/hub_location.py) |
| hydrogen_energy_hub_location | 水素エネルギーハブ (再エネ・電解槽・貯蔵) 最適配置・サイジングモデル (MINLP) — 再生可能エネルギー（太陽光・風力）の出力変動を吸収し、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/hydrogen_energy_hub_location.py) |
| microgrid_cgs_network_synthesis | 分散型マイクログリッドにおける熱電融通ネットワークとコージェネ配置 (MINLP) — 複数のビルや施設からなる地域コミュニティ（マイクログリッド）において、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/microgrid_cgs_network_synthesis.py) |
| railway_energy_storage_location | 鉄道における地上蓄電設備(WESS) 最適配置・サイジングモデル (MILP) — 列車の回生ブレーキによって発生する電力が、他の力行中の列車によって | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/railway_energy_storage_location.py) |
| railway_substation_location_power_flow | 直流電気鉄道の変電所 最適配置・サイジング問題 (MINLP) — 路線上の複数の候補地から、直流変電所（TSS: Traction Substation）を | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/railway_substation_location_power_flow.py) |
| transmission_expansion | 送電線拡張計画 (Transmission Expansion Planning, 簡易版) — 送配電事業者の系統計画担当者が、複数の候補送電線候補の中から新設するコリドーを選び、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/transmission_expansion.py) |

[← カタログ全体へ戻る](index.md)
