# エネルギー・マイクログリッド

発電・蓄電・熱・水素の需給運用と設計。UC(起動停止)、蓄電池ディスパッチ、AC/DC 潮流、マイクログリッド設計など、二次燃料費や潮流の非凸を含むモデル群。

**16 本**(うち旗艦 ⭐ 4 本) / `scale` 引数対応 6 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| ⭐ **ac_opf** | 交流最適潮流(AC-OPF)+ 離散無効電力補償 (AC Optimal Power Flow, MINLP). — 送電系統運用者(ISO/RTO・電力会社の給電指令所)が、各発電機の有効/無効出力と | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/ac_opf.py) |
| ⭐ **hydro_cascade_efficiency** | 水頭依存効率を持つ多段ダム放流計画 (Hydro Cascade with Head-Dependent Efficiency). — 一級河川に連なる複数ダムを一括運用する電力会社の「水系運用担当者」が、季節(数十〜 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/hydro_cascade_efficiency.py) |
| ⭐ **microgrid_design_operation** | マイクログリッド設計 + 複数代表日運用の同時決定 (Microgrid Design & Multi-Day Operation). — オフグリッド化を検討する工業団地の「マイクログリッド設計者」が、太陽光(PV)・ | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/microgrid_design_operation.py) |
| ⭐ **weekly_uc_ramp** | 週次ユニットコミットメント + 送電混雑(簡易DC潮流) (Weekly UC with Network Congestion). — 電力会社の「需給運用部」が、翌週(168時間)の発電ユニット群の起動/停止・出力配分を | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/weekly_uc_ramp.py) |
| battery_degradation_dispatch | サイクル劣化コストを内生化した蓄電池アービトラージ運用 (Battery Degradation-Aware Dispatch). — 系統に連系したスタンドアロン蓄電池(BESS)の「運用者」が、電力市場の時間帯別価格 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/battery_degradation_dispatch.py) |
| district_heating_grid | 地域冷暖房配管網熱供給計画 (District Heating Grid) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/district_heating_grid.py) |
| ev_charging_fleet | 電気自動車充電フリートスケジューリング (EV Charging Fleet Scheduling) — 夜間に帰着する配送用の電気自動車 (EV) フリートを対象とし、翌朝の出発時間までに | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/ev_charging_fleet.py) |
| ev_charging_network | EV都市充電スタンド配置最適化 (EV Charging Network Design) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/ev_charging_network.py) |
| geothermal_heat_pump | 地熱ヒートポンプCOP最適化運転 (Geothermal Heat Pump) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/geothermal_heat_pump.py) |
| hydro_thermal_coordination | 水火力電源協調運転計画 (Hydro-Thermal Coordination) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/hydro_thermal_coordination.py) |
| microgrid_ems | Microgrid Energy Management System (EMS) — This model optimizes the scheduling of a microgrid containing a diesel generator, solar… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/microgrid_ems.py) |
| microgrid_islanded | 孤立型マイクログリッド運転計画 (Islanded Microgrid) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/microgrid_islanded.py) |
| solar_pv_inverter | 太陽光インバータ無効電力最適化 (Solar PV Inverter Reactive Power) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/solar_pv_inverter.py) |
| thermal_storage_lossy | 槽外温度差の非線形熱損失を持つ蓄熱運用 (Thermal Storage with Nonlinear Ambient-Loss). — 地域熱供給/工場蒸気系統に付随する複数の蓄熱槽(温水タンク)を運用する「蓄熱運用者」が、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/thermal_storage_lossy.py) |
| virtual_power_plant | 仮想発電所 (VPP) 入札・制御最適化 (Virtual Power Plant Control) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/virtual_power_plant.py) |
| wind_battery_dispatch | 風力発電と蓄電池の協調制御 (Wind and Battery Dispatch) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/energy_and_microgrid/wind_battery_dispatch.py) |

[← カタログ全体へ戻る](index.md)
