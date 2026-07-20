# 受け入れ検証結果 (Phase 13)

`experiments/acceptance.py` による自動判定。

- 小scale=`small`(最適到達確認, <= 120s) / 既定scale=`default`(30s analyze)
- 受け入れ基準: **30秒で gap>=10%** または **非自明findings発火**(symmetry_info/decomposable 以外)
- 判定: **3/3 PASS**

| model | small status | small obj | small(s) | default gap | nodes | nsols | findings | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| petroleum_pooling | optimal | 1.844e+04 | 0.4 | 3.8% | 222 | 3 | `numerical_scale` | ✅ PASS |
| foundry_charge_mix_multiperiod | optimal | 3.656e+04 | 0.0 | 52.5% | 5007 | 12 | `dual_stall` | ✅ PASS |
| water_network_reuse | optimal | 156.9 | 38.5 | 24.3% | 2960 | 30 | `numerical_scale`, `decomposable` | ✅ PASS |

判定理由(PASS根拠):
- **petroleum_pooling**: 非自明findings numerical_scale
- **foundry_charge_mix_multiperiod**: gap 52.5% ≥ 10%; 非自明findings dual_stall
- **water_network_reuse**: gap 24.3% ≥ 10%; 非自明findings numerical_scale

## 調整の試行錯誤で分かった知見

- **プーリングは「双対gap」より「primal(可行解発見)」が難所**: 濃度×流量の双線形*等式*系は
  SCIPがincumbentを見つけること自体が難しく、規格をタイト化しすぎると30秒で可行解ゼロになる
  (=既定scaleの要件「実行可能解が出る」を破る)。**高コストのスポット市場調達を実行可能性の
  バックストップ**として入れると常に可行解を持ち、双線形プーリングはコスト削減レバーとして残る。
  現行defaultは numerical_scale(take-or-payのbig-M)で発火してPASS(analyzeのpresolveが良い
  incumbentを見つけるため最終gapは3.8%と小さめだが、非自明findingで題材性は担保)。
- **純粋な整数×連続(分離可能)はSCIPのOBBT/伝播がルートで潰す**(FINDINGS 4節どおり)。
  foundryは当初 n×s だけで scale を上げても gap 0 だった。**溶湯組成を変数化(濃度×質量・濃度×配分の
  双線形)して注文間を共通溶湯で結合**させ、規格窓を狭く・銅上限をタイト・スクラップ在庫を希少化した
  ところで gap 52% に。結合した双線形でないと gap は残らない。
- **水ネットワークは淡水を高コスト化して再利用を必須化**するまで gap が出ない(淡水が安いと再利用=
  双線形が働かず near-linear)。fresh=25/disch=15、入口濃度上限を20-120ppmにタイト化、再生費を
  凹 TT^0.7 で持つと default gap 24%。smallは nP=4 だと120秒でも証明できず、**nP=3 に下げて39秒で最適証明**。
