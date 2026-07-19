# 診断センサス(サンプル群のベンチマーク)

minlpkit の診断エンジン(`mk.analyze`)を samples の多数のモデルに一括適用し、どの症状(finding)がどのモデルで発火するかを棚卸しした結果。サンプル群を「診断のベンチマーク=センサス」として使う。

- 対象カテゴリ: energy_and_microgrid, packing_and_cutting, physics_and_control_minlp, scheduling
- 各モデル `mk.analyze(build_model, time_limit=10)` を1回実行
- 全 50 本中 解析成功 47 本 / skip 1 本 / error 2 本

再現: `uv run python experiments/run_census.py --time 10`


## 集計1: finding別 発火件数

| finding id | 重要度 | 発火本数 |
| --- | --- | --- |
| `symmetry_info` | good | 23 |
| `decomposable` | good | 9 |
| `numerical_scale` | warning | 7 |
| `weak_relaxation` | serious | 1 |
| `wide_term_range` | warning | 0 |
| `dual_stall` | warning | 0 |
| `gpu_primal` | warning | 0 |

## 集計2: 難しいモデル上位(残存gap大)

| sample | category | gap | nodes | nsols | findings |
| --- | --- | --- | --- | --- | --- |
| chp_plant_synthesis_minlp | physics_and_control_minlp | 1.0% | 1.0 | 2.0 | decomposable |
| unit_commitment | scheduling | 0.9% | 1.0 | 4.0 | numerical_scale |
| power_aware_scheduling | scheduling | 0.8% | 81.0 | 7.0 | numerical_scale;symmetry_info |
| railway_substation_coordination_minlp | physics_and_control_minlp | 0.6% | 1.0 | 1.0 | numerical_scale |
| data_center_cooling_power_minlp | physics_and_control_minlp | 0.5% | 1.0 | 4.0 | decomposable |
| industrial_complex_energy_system_minlp | physics_and_control_minlp | 0.0% | 1.0 | 2.0 | numerical_scale |
| pwl_sos | physics_and_control_minlp | 0.0% | 1.0 | 1.0 | decomposable |
| heat_exchanger_network | physics_and_control_minlp | 0.0% | 1.0 | 3.0 | — |
| refinery_blending | physics_and_control_minlp | 0.0% | 1.0 | 2.0 | decomposable |
| thermal_battery_hybrid | physics_and_control_minlp | 0.0% | 1.0 | 1.0 | symmetry_info |

## 集計3: 非線形モデルでの weak_relaxation 発火率

- 非線形モデル(`has_nonlinear=True`)は 11 本。うち `weak_relaxation` 発火は 1 本(**9%**)。

発火モデル: `district_heating_detailed_physics`


## 全結果表

| sample | category | status | gap | nodes | nsols | nl | findings | note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| district_heating_grid | energy_and_microgrid | optimal | 0.0% | 0.0 | 1.0 |  | — |  |
| ev_charging_fleet | energy_and_microgrid | optimal | 0.0% | 1.0 | 4.0 |  | symmetry_info |  |
| ev_charging_network | energy_and_microgrid | optimal | 0.0% | 0.0 | 2.0 |  | — |  |
| geothermal_heat_pump | energy_and_microgrid | optimal | 0.0% | 0.0 | 1.0 |  | — |  |
| hydro_thermal_coordination | energy_and_microgrid | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info |  |
| microgrid_ems | energy_and_microgrid | optimal | 0.0% | 1.0 | 1.0 |  | — |  |
| microgrid_islanded | energy_and_microgrid | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info |  |
| solar_pv_inverter | energy_and_microgrid | optimal | 0.0% | 1.0 | 3.0 | ✓ | — |  |
| virtual_power_plant | energy_and_microgrid | optimal | 0.0% | 0.0 | 2.0 |  | symmetry_info |  |
| wind_battery_dispatch | energy_and_microgrid | optimal | 0.0% | 1.0 | 2.0 |  | — |  |
| bin_packing_2d | packing_and_cutting | optimal | 0.0% | 1.0 | 2.0 |  | symmetry_info |  |
| cutting_stock | packing_and_cutting | skip | — | — | — | — | — | build_model無し |
| cutting_stock_advanced | packing_and_cutting | optimal | 0.0% | 10.0 | 13.0 |  | symmetry_info;decomposable |  |
| gap_large | packing_and_cutting | no-gap | — | 1.0 | 2.0 |  | symmetry_info |  |
| glass_cutting_2d | packing_and_cutting | optimal | 0.0% | 1.0 | 2.0 | ✓ | numerical_scale |  |
| knapsack | packing_and_cutting | optimal | 0.0% | 0.0 | 2.0 |  | symmetry_info;decomposable |  |
| mkp | packing_and_cutting | optimal | 0.0% | 1.0 | 4.0 |  | decomposable |  |
| molded_parts_cutting | packing_and_cutting | optimal | 0.0% | 0.0 | 2.0 |  | symmetry_info |  |
| warehouse_slotting | packing_and_cutting | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info |  |
| chp_plant_synthesis_minlp | physics_and_control_minlp | gap 1.0% | 1.0% | 1.0 | 2.0 | ✓ | decomposable |  |
| data_center_cooling_power_minlp | physics_and_control_minlp | gap 0.5% | 0.5% | 1.0 | 4.0 | ✓ | decomposable |  |
| district_heating_detailed_physics | physics_and_control_minlp | optimal | 0.0% | 73.0 | 16.0 | ✓ | weak_relaxation;numerical_scale |  |
| heat_exchanger_network | physics_and_control_minlp | optimal | 0.0% | 1.0 | 3.0 | ✓ | — |  |
| industrial_complex_energy_system_minlp | physics_and_control_minlp | gap 0.0% | 0.0% | 1.0 | 2.0 | ✓ | numerical_scale |  |
| pwl_sos | physics_and_control_minlp | optimal | 0.0% | 1.0 | 1.0 |  | decomposable |  |
| railway_power_flow_scheduling | physics_and_control_minlp | optimal | 0.0% | 1.0 | 2.0 | ✓ | numerical_scale |  |
| railway_substation_coordination_minlp | physics_and_control_minlp | gap 0.6% | 0.6% | 1.0 | 1.0 | ✓ | numerical_scale |  |
| refinery_blending | physics_and_control_minlp | optimal | 0.0% | 1.0 | 2.0 | ✓ | decomposable |  |
| thermal_battery_hybrid | physics_and_control_minlp | optimal | 0.0% | 1.0 | 1.0 |  | symmetry_info |  |
| airline_overbooking | scheduling | optimal | 0.0% | 0.0 | 3.0 |  | — |  |
| airport_gate_assignment | scheduling | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info |  |
| assembly_line | scheduling | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info |  |
| assembly_line_balancing_2 | scheduling | optimal | 0.0% | 1.0 | 3.0 |  | — |  |
| battery_train_scheduling | scheduling | optimal | 0.0% | 1.0 | 2.0 |  | symmetry_info |  |
| bus_driver_rostering | scheduling | optimal | 0.0% | 1.0 | 1.0 |  | symmetry_info |  |
| cement_mill_scheduling | scheduling | optimal | 0.0% | 0.0 | 1.0 |  | symmetry_info;decomposable |  |
| hydro_scheduling | scheduling | optimal | 0.0% | 1.0 | 2.0 |  | symmetry_info |  |
| job_shop | scheduling | optimal | 0.0% | 1.0 | 3.0 |  | — |  |
| job_shop_flexible | scheduling | optimal | 0.0% | 0.0 | 2.0 |  | — |  |
| maintenance_production_scheduling | scheduling | optimal | 0.0% | 1.0 | 43.0 |  | symmetry_info;decomposable |  |
| power_aware_scheduling | scheduling | gap 0.8% | 0.8% | 81.0 | 7.0 |  | numerical_scale;symmetry_info |  |
| rcpsp | scheduling | skip | — | — | — | — | — | 非対応の制約式によるパースエラー |
| sequence_dependent_flowshop | scheduling | optimal | 0.0% | 47.0 | 4.0 |  | symmetry_info |  |
| shift_scheduling | scheduling | optimal | 0.0% | 1.0 | 4.0 |  | — |  |
| sports_scheduling | scheduling | optimal | 0.0% | 1.0 | 1.0 |  | symmetry_info |  |
| stn_batch_scheduling | scheduling | optimal | 0.0% | 1.0 | 2.0 |  | symmetry_info |  |
| traffic_light_sync | scheduling | optimal | 0.0% | 0.0 | 2.0 |  | — |  |
| train_rescheduling_disruption | scheduling | optimal | 0.0% | 1.0 | 11.0 |  | symmetry_info |  |
| train_scheduling | scheduling | skip | — | — | — | — | — | モデル構築時の変数未定義エラー |
| unit_commitment | scheduling | gap 0.9% | 0.9% | 1.0 | 4.0 | ✓ | numerical_scale |  |
