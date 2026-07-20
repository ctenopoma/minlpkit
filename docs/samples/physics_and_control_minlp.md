# 物理・制御 MINLP

熱交換網・精製ブレンド・地域熱供給など、双線形/指数/有理式の物理法則を組み込んだ非凸 MINLP。空間分枝と緩和の締めの主戦場。

**11 本**(うち事業ストーリーが特に詳しいもの ⭐ 2 本) / `scale` 引数対応 2 本。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| ⭐ **district_heating_detailed_physics** | 地域熱供給網 (District Heating Network) の詳細物理最適化モデル (MINLP) — 地域熱供給事業者の「プラント運転員」が、熱源プラントから放射状(木構造)に広がる配管網を通じて複数需要家へ熱を届けるための、各期(時間帯)ごとの質量流量・温度・熱源出力・ポンプ動力を決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/district_heating_detailed_physics.py) |
| ⭐ **water_network_reuse** | 工場内 用水・再利用ネットワーク (Industrial Water Reuse Network Synthesis). — 化学/製紙/半導体などの工場の「ユーティリティ設計チーム」が、複数の水使用プロセス(洗浄・冷却・反応など)の間に**再利用配管**をどう敷設し、各プロセスへ淡水・再利用水・再生水をどう配分するかを決め、**淡水購入費と排水処理費と設備費を最小化**する意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/water_network_reuse.py) |
| chp_plant_synthesis_minlp | 熱電併給(CHP)プラントのスーパー構造ベース合成最適化 (MINLP) — ガスタービン(GT)、排熱回収ボイラー(HRSG)、蒸気タービン(ST)、および補助ボイラーからなる | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/chp_plant_synthesis_minlp.py) |
| data_center_cooling_power_minlp | データセンターのITジョブと冷却・電力システムの連成最適化 (MINLP) — 大量の電力を消費するデータセンターにおいて、計算ジョブ（バッチ処理）の | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/data_center_cooling_power_minlp.py) |
| heat_exchanger_network | 熱交換ネットワーク合成問題 (Heat Exchanger Network Synthesis - HENS) — 化学プロセス設計において、エネルギー消費量（外部ユーティリティ使用量）と | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/heat_exchanger_network.py) |
| industrial_complex_energy_system_minlp | 大規模複合施設向け 統合エネルギーシステム最適化 (MINLP) — 大量の電力と冷温熱を消費する大規模施設（工場や大型商業施設）を対象に、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/industrial_complex_energy_system_minlp.py) |
| pwl_sos | 非凸関数の区分線形近似 (SOS2 vs Big-M) — SOS制約の実証用 — 非凸な1変数関数 f(x) を区分線形(PWL)近似して最小化する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/pwl_sos.py) |
| railway_power_flow_scheduling | 直流電気鉄道の運行スケジュールと潮流計算(Power Flow)の統合最適化 (MINLP) — 列車の運行スケジュール（速度プロファイル、力行・惰行・減速モード）と、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/railway_power_flow_scheduling.py) |
| railway_substation_coordination_minlp | 直流電気鉄道の変電所間協調電圧制御 (Substation Cooperative Control) MINLP — 通常、直流変電所(TSS)は固定の無負荷送り出し電圧（例: 1500V）で運転されますが、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/railway_substation_coordination_minlp.py) |
| refinery_blending | 石油精製所におけるブレンドスケジューリング (Refinery Blending / Pooling Problem) — 複数の原料（原油や留分）を中間プールタンクに一度貯蔵し、それらを再度ブレンドして | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/refinery_blending.py) |
| thermal_battery_hybrid | 蓄熱・蓄電ハイブリッドエネルギー管理システム (Thermal and Battery Hybrid EMS) — 自家発電設備（熱電併給コジェネレーション: CHP）、蓄電池（BESS）、蓄熱槽（TES）、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/physics_and_control_minlp/thermal_battery_hybrid.py) |

[← カタログ全体へ戻る](index.md)
