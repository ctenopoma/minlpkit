# Phase 16 バッチ2: 精緻化結果記録

対象10本。基準は task.md Phase 16節(docstring 2-4文+モデルのリアリズム底上げ、軽量)。
変数・制約数は presolve 前の `build_model()` 直後の値(`len(m.getVars())` / `len(m.getConss())`)。
動作確認は `limits/time=30` 秒、`hideOutput()` で全10本個別実行し記録。

| # | ファイル | before(変数/制約) | after(変数/制約) | 新docstring要約 | 動作確認 |
|---|---|---|---|---|---|
| 1 | samples/routing_and_logistics/cross_docking.py | 4 / 2 | 30 / 20 | クロスドックのドア割当(入荷/出荷×ドア容量)+品目別仕分けフローの同時決定 | optimal, obj=570.0 |
| 2 | samples/energy_and_microgrid/district_heating_grid.py | 2 / 2 | 24 / 20 | 複数熱源×複数時間帯の稼働(整数)+出力配分、配管摩擦損失は流量2乗の非線形 | optimal, obj=8968.16 |
| 3 | samples/finance_and_pricing/dynamic_pricing_hotel.py | 3 / 2 | 18 / 22 | 部屋タイプ×曜日区分の動的価格(双線形収益)+週末/繁忙日の価格順序ルール | optimal, obj=16786.21 |
| 4 | samples/energy_and_microgrid/ev_charging_network.py | 1 / 1 | 16 / 12 | 候補地の充電器基数(整数)決定+カバー圏内エリアへの供給配分 | optimal, obj=207999.99... |
| 5 | samples/location_and_network_design/facility_location_capacitated.py | 6 / 5 | 27 / 14 | 拠点開設(持続的投資)+繁忙期/閑散期2期の需要充足配分 | optimal, obj=13460.0 |
| 6 | samples/manufacturing_and_blending/foundry_charge_mix.py | 2 / 2 | 13 / 17 | 単期4ロット×2注文のヒート回数×装入量(双線形)+成分規格+外注バックストップ | optimal, obj=9400.0 |
| 7 | samples/location_and_network_design/gas_network_opt.py | 3 / 2 | 13 / 12 | 直列2区間Weymouth式(流量^2=K*圧力差)+バイパス管建設投資(整数)×2期需要 | optimal, obj=24.59 |
| 8 | samples/energy_and_microgrid/geothermal_heat_pump.py | 2 / 2 | 24 / 21 | 複数井×複数期のオンオフ(整数)+COP(出湯温度)×電力=供給熱量の双線形 | optimal, obj=1364.21 |
| 9 | samples/packing_and_cutting/glass_cutting_2d.py | 3 / 2 | 14 / 9 | 2種定尺原板の面積ベース歩留まりカット(整数枚数)+特注品寸法(双線形面積) | optimal, obj=1180.0 |
| 10 | samples/routing_and_logistics/hub_and_spoke.py | 1 / 1 | 24 / 17 | p-ハブ・メディアン簡略版: ハブ開設上限+割当+容量+幹線コスト規模の経済 | optimal, obj=3624.0 |

## 検証コマンド

各ファイルを `importlib` で個別ロードし、`build_model()` → `setParam('limits/time', 30)` →
`optimize()` を実行。全10本 `status: optimal` を30秒以内(実際は数秒未満)で確認。

## 備考

- `foundry_charge_mix.py` は同ディレクトリの `foundry_charge_mix_multiperiod.py`(T1旗艦)とは
  別ファイルであり、旗艦側は一切編集していない。
- `gas_network_opt.py` は既存の Weymouth 双線形(flow^2=K*Δp)構造を維持しつつ、直列2区間+
  バイパス投資判断+2期需要へ拡張した。
- 全10本とも `pyscipopt.Model` / `quicksum` のみ使用、新規依存追加なし。
