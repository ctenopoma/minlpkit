# サンプルカタログ

minlpkit に同梱する **129 本**の MINLP/MILP サンプルモデルをカテゴリ別に一覧化したカタログです(scikit-learn の Example gallery に相当)。
各サンプルは実在する事業課題を題材にした `build_model()` を持ち、可視化・診断・改善手法の検証台として使えます。実行結果を見たい場合は[成果ギャラリー](../gallery.md)を参照。
説明文は各ファイルのモジュール docstring から自動抽出しています(再生成: `uv run python experiments/gen_sample_catalog.py`)。

⭐ マークは事業ストーリーが特に詳しいサンプル(11 本)を示す。そのうち一部は、事業ストーリー→素朴な定式化→診断→改善を1本の物語として実行できる学習用 notebook(`docs/notebooks/samples/`)が付属する(下表で「notebook」リンクがあるものが該当)。

## カテゴリ一覧

| カテゴリ | 本数 | ⭐ | 概要 |
| --- | :---: | :---: | --- |
| [スケジューリング](scheduling.md) | 21 | — | ジョブショップ・シフト・保守・列車運行など時間軸の割当計画。 |
| [エネルギー・マイクログリッド](energy_and_microgrid.md) | 16 | 4 | 発電・蓄電・熱・水素の需給運用と設計。 |
| [経路・物流](routing_and_logistics.md) | 16 | — | 配送・巡回・車両割当・在庫輸送。 |
| [立地・ネットワーク設計](location_and_network_design.md) | 14 | 3 | 施設配置・送電/ガス/水素ネットワーク設計。 |
| [その他(基礎・拡張題材)](others.md) | 12 | — | スケジューリングの基礎版やプラント物理入り拡張など、可視化・診断のベースライン比較に使う題材。 |
| [グラフ・離散構造](graph_and_discrete.md) | 11 | — | 彩色・被覆・分割・マッチングなど、グラフ/組合せ構造の離散最適化。 |
| [物理・制御 MINLP](physics_and_control_minlp.md) | 11 | 2 | 熱交換網・精製ブレンド・地域熱供給など、双線形/指数/有理式の物理法則を組み込んだ非凸 MINLP。 |
| [製造・ブレンド](manufacturing_and_blending.md) | 10 | 2 | 配合・プーリング・鋳造チャージ。 |
| [金融・価格設計](finance_and_pricing.md) | 9 | — | ポートフォリオ選択・価格付け・収益管理。 |
| [パッキング・カッティング](packing_and_cutting.md) | 9 | — | ナップサック・ビンパッキング・カッティングストック。 |
| **合計** | **129** | **11** | |

## 事業ストーリーが特に詳しいサンプル(⭐)

事業ストーリー→素朴な定式化→診断→改善を1本の物語として追える題材。「notebook」リンクがあるものは、その物語をそのまま実行できる学習用 notebook が付属する。

| サンプル | カテゴリ | 事業ストーリー | ソース |
| --- | --- | --- | :---: |
| **ac_opf** ([notebook](../notebooks/samples/ac_opf.ipynb)) | [エネルギー・マイクログリッド](energy_and_microgrid.md) | 交流最適潮流(AC-OPF)+ 離散無効電力補償 (AC Optimal Power Flow, MINLP). — 送電系統運用者(ISO/RTO・電力会社の給電指令所)が、各発電機の有効/無効出力と各バスの電圧を決め、需要を満たしながら**発電費用**(または送電損失)を最小化する意思決定である。T2 `weekly_uc_ramp.py` の簡易DC潮流(有効電力のみ・線形)を、**真の交流(AC)潮流**へ格上げした対比題材に位置づける。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/ac_opf.py) |
| **hydro_cascade_efficiency** ([notebook](../notebooks/samples/hydro_cascade_efficiency.ipynb)) | [エネルギー・マイクログリッド](energy_and_microgrid.md) | 水頭依存効率を持つ多段ダム放流計画 (Hydro Cascade with Head-Dependent Efficiency). — 一級河川に連なる複数ダムを一括運用する電力会社の「水系運用担当者」が、季節(数十〜百数十日)にわたる各ダムの放流量を決める意思決定である。上流ダムの放流は下流ダムへの流入となり(河川流下の時間遅れを伴う)、各ダムの発電量は「放流量 × 水頭(貯水位に依存)」という**双線形**で決まる。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/hydro_cascade_efficiency.py) |
| **microgrid_design_operation** ([notebook](../notebooks/samples/microgrid_design_operation.ipynb)) | [エネルギー・マイクログリッド](energy_and_microgrid.md) | マイクログリッド設計 + 複数代表日運用の同時決定 (Microgrid Design & Multi-Day Operation). — オフグリッド化を検討する工業団地の「マイクログリッド設計者」が、太陽光(PV)・蓄電池・非常用発電機の設備容量(サイジング)と、季節を代表する複数の代表日(夏平日・冬平日・中間期・週末など)にわたる充放電・出力配分(運用)を同時に決める投資意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/microgrid_design_operation.py) |
| **weekly_uc_ramp** ([notebook](../notebooks/samples/weekly_uc_ramp.ipynb)) | [エネルギー・マイクログリッド](energy_and_microgrid.md) | 週次ユニットコミットメント + 送電混雑(簡易DC潮流) (Weekly UC with Network Congestion). — 電力会社の「需給運用部」が、翌週(168時間)の発電ユニット群の起動/停止・出力配分を決める意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/weekly_uc_ramp.py) |
| **gas_pipeline_weymouth** | [立地・ネットワーク設計](location_and_network_design.md) | ガス圧送ネットワークの運用計画 (Gas Pipeline Network with Weymouth Flow-Pressure). — 都市ガス/天然ガス輸送会社の「圧送運用部」が、1日(または数日)を通じて、供給拠点からの基本供給量、各コンプレッサ(圧送機)の起動/停止と昇圧量、そして緊急時の局所ピークシェイビング供給を決める意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/gas_pipeline_weymouth.py) |
| **hydrogen_hub_transport** | [立地・ネットワーク設計](location_and_network_design.md) | 水素サプライチェーン: ハブ配置 + 多期輸送計画 (Hydrogen Hub Location & Transport). — 水素サプライチェーンを構築するエネルギー事業者の「計画担当者」が、候補地の中から「どこに生産・貯蔵ハブを開設し、どれだけの生産・貯蔵容量を持たせるか」(整数の開設可否 + 連続の容量)を決め、開設したハブから複数の需要地(水素ステーション等)へ「複数期にわたってどれだけ輸送するか」(連続)を同時に決める投資・運用意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/hydrogen_hub_transport.py) |
| **transmission_expansion_operation** ([notebook](../notebooks/samples/transmission_expansion_operation.ipynb)) | [立地・ネットワーク設計](location_and_network_design.md) | 送電線増強計画 + 増強後運用の同時決定 (Transmission Expansion Planning with Operation). — 電力広域系統運用機関の「系統計画者」が、複数年に一度の投資計画サイクルで「どの候補送電線(コリドー)を新設・増強するか」(整数)を決め、その増強後の系統で「複数の需要シナリオそれぞれに対する給電運用(DC潮流)」(連続)を同時に検討する意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/location_and_network_design/transmission_expansion_operation.py) |
| **foundry_charge_mix_multiperiod** ([notebook](../notebooks/samples/foundry_charge_mix_multiperiod.ipynb)) | [製造・ブレンド](manufacturing_and_blending.md) | 鋳造の多期チャージ配合計画 (Multi-period Foundry Charge Mix). — 電気炉(EAF)を持つ鋳物工場の「溶解計画係」が、数日〜1週間の計画期間について、各時間帯(期)に「どの注文グレードの溶湯を、何回(整数)、1回あたり何トン(連続)溶かし、その各チャージにスクラップ在庫のどのロットを何トン投入するか」を決める意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/foundry_charge_mix_multiperiod.py) |
| **petroleum_pooling** ([notebook](../notebooks/samples/petroleum_pooling.ipynb)) | [製造・ブレンド](manufacturing_and_blending.md) | 石油調達→プーリング→製品ブレンドの多期計画 (Multi-period Petroleum Pooling). — 中堅の石油精製・調達会社の「調達計画部」が、数週間の計画期間について、どの原料(スイート/サワー原油・各種留分)を、いつ、どれだけ買い付け、どの中間タンク(プール)に入れ、そこからどの製品(プレミアム/レギュラー等)へブレンドするかを決める意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/petroleum_pooling.py) |
| **district_heating_detailed_physics** | [物理・制御 MINLP](physics_and_control_minlp.md) | 地域熱供給網 (District Heating Network) の詳細物理最適化モデル (MINLP) — 地域熱供給事業者の「プラント運転員」が、熱源プラントから放射状(木構造)に広がる配管網を通じて複数需要家へ熱を届けるための、各期(時間帯)ごとの質量流量・温度・熱源出力・ポンプ動力を決める意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/district_heating_detailed_physics.py) |
| **water_network_reuse** | [物理・制御 MINLP](physics_and_control_minlp.md) | 工場内 用水・再利用ネットワーク (Industrial Water Reuse Network Synthesis). — 化学/製紙/半導体などの工場の「ユーティリティ設計チーム」が、複数の水使用プロセス(洗浄・冷却・反応など)の間に**再利用配管**をどう敷設し、各プロセスへ淡水・再利用水・再生水をどう配分するかを決め、**淡水購入費と排水処理費と設備費を最小化**する意思決定である。 | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/water_network_reuse.py) |

