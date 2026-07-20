# 受け入れ検証結果 (Phase 13)

`experiments/acceptance.py` による自動判定。

- 小scale=`small`(最適到達確認, <= 120s) / 既定scale=`default`(30s analyze)
- 受け入れ基準: **30秒で gap>=10%** または **非自明findings発火**(symmetry_info/decomposable 以外)
- 判定: **3/3 PASS**

| model | small status | small obj | small(s) | default gap | nodes | nsols | findings | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| production_distribution_integrated | optimal | 1.207e+04 | 0.6 | 77.1% | 1 | 3 | `symmetry_info` | ✅ PASS |
| multi_echelon_inventory_realistic | optimal | 3529 | 0.9 | 4.2% | 3520 | 100 | `numerical_scale`, `symmetry_info` | ✅ PASS |
| maritime_inventory_routing_realistic | optimal | 977.8 | 7.0 | 19.4% | 42 | 100 | `dual_stall`, `symmetry_info` | ✅ PASS |

判定理由(PASS根拠):
- **production_distribution_integrated**: gap 77.1% ≥ 10%
- **multi_echelon_inventory_realistic**: 非自明findings numerical_scale
- **maritime_inventory_routing_realistic**: gap 19.4% ≥ 10%; 非自明findings dual_stall

## 調整の試行錯誤で分かった知見(T4)

- **固定費用ネットワークフロー型のMILP(生産ロットサイジング+車両割当)はSCIPに
  異常なほど強く、共有資源をどれだけタイト化しても root node(nodes=1)で
  gap<1%まで収束してしまう**: `production_distribution_integrated` は当初
  T1-T3の手法(big-Mのタイト化、共有トラック車隊のタイト化、生産能力の
  タイト化)を一通り試したが、fleet比率0.72→0.38、生産能力1.15倍→1.06倍と
  タイトにしても gap は常に1%未満だった(ネットワークフロー構造は多数の
  レーン・期にまたがる連続変数の「ならし効果」でLP緩和が自己平均化され、
  各レーンの端数誤差が全体コストに対して希釈されるため)。さらに
  ドライバー労務時間という第2の独立なタイト共有資源(多次元ナップサック化)
  を追加しても効果は無かった。**唯一有効だったのは変数・制約規模を
  純粋に拡大すること**(工場9×DC16×期14、4634変数)で、30秒では
  root LPの求解自体が終わらず(`solve_time=30.0秒`張り付き、`nsols=3`)、
  結果gap 77.1%でPASSした。これはT2教訓3(`mk.analyze`のセットアップ
  コスト乗算)と表面的には同じ「大規模化」だが、狙いは逆で「非線形
  収集器のコスト」ではなく「LPソルブそのものの時間」を意図的に使い切る
  難度源泉であり、T1-T3にはなかった**T4固有の教訓**。
- **numerical_scale(big-M残存)は純粋MILPでは狙って発火させにくい**:
  T1のpetroleum_poolingのnumerical_scaleは非凸双線形制約が原因でSCIPの
  presolveがbig-Mを完全には縮小できなかったために生じたが、
  `production_distribution_integrated` で同様の「段取りゲートのbig-M」を
  緩く設定しても、線形モデルではSCIPのbound-tightening presolveが
  他の制約(実効生産能力の上限)から間接的に真の上限を導出し、big-Mを
  完全に締めてしまう(`residual_bigm_count=0`)。全て非負変数・線形制約の
  場合、どんな集約制約も「他変数=0」で単変数の上限に帰着できてしまうため、
  純粋MILPでbig-M残存を作るのは非凸性が無いと本質的に困難という知見を
  得た(T1-T3の`numerical_scale`は全て非凸(双線形)または大規模(送電線)
  モデルに由来しており、純粋な小〜中規模MILPでは別の非自明finding
  (`symmetry_info`は自明なので不可)かgap自体を稼ぐ必要がある)。
- **多段階在庫(multi_echelon_inventory_realistic)は当初DC在庫がマイナスに
  なりうる不整合な定式化だった**: 小売の発注量をDCの手持ち在庫と無関係に
  `ship_r == lot_r * n_r` で確定させたところ、DC側の在庫バランス式が
  理論上負値を要求しうる(DCの在庫下限0とのハード制約と矛盾し infeasible
  リスク)ことに気づき、DCの緊急補充バックストップ変数 `emerg_dc`(高コスト
  特急便)を追加して常時実行可能性を確保した。T1-T3で繰り返し確認された
  「バックストップは他制約と整合しないと機能しない」教訓が、多段階在庫の
  発注-在庫デカップリングという新しい形で再現された。
- **maritime_inventory_routing_realistic は当初、船隊の総輸送能力
  (容量÷航海サイクル)が港湾の総消費量を大きく上回っており(896 vs 595)、
  root nodeで即座に解けていた(gap 0.6%)**: 船隊の総スループット
  (`Σ cap_v/transit_v`)と港湾の総消費量をほぼ拮抗させる(94%)ようデータ
  生成式を変更したところ、船腹の奪い合いが常時タイトな bin-packing的
  組合せ判断になり、gap 19.4%・`dual_stall` でPASSした。既存
  `maritime_inventory_routing.py`(Phase16、期あたり隻数の集計変数)とは
  異なり、本モデルは個々の船の航海サイクル(時間結合)を明示することで
  T4の題材要件(「複数港が同じ船隊を取り合う構造」)を素直に満たせた。
- **横断的な教訓**: T1(双線形の実行可能性)・T2(`mk.analyze`のセットアップ
  コスト)・T3(big-M disjunctiveが根ノードで解かれやすい)に続き、T4では
  「共有資源をタイト化するだけでは純粋MILP・多数レーン型ネットワークフロー
  の難度は上がらず、真に効くのは(a)問題規模そのものを拡大してLPソルブ
  時間を使い切る、(b)資源の需給バランスを臨界点(94%前後)まで詰めて
  bin-packing的な組合せ判断を作る、のいずれか」という**T4固有の教訓**を
  得た。numerical_scaleは非凸モデル(T1)や大規模disjunctiveモデル(T2/T3)
  由来のfindingであり、小〜中規模の純粋MILPでは狙って発火させにくい
  ことも合わせて明示しておく。
