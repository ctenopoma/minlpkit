# 製造・ブレンド

配合・プーリング・鋳造チャージ。濃度×流量の双線形(プーリング)を核とするプロセス産業のバッチ/多期モデル群。

**10 本**(うち旗艦 ⭐ 2 本) / `scale` 引数対応 4 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| ⭐ **foundry_charge_mix_multiperiod** ([学習notebook](../notebooks/samples/foundry_charge_mix_multiperiod.ipynb)) | 鋳造の多期チャージ配合計画 (Multi-period Foundry Charge Mix). — 電気炉(EAF)を持つ鋳物工場の「溶解計画係」が、数日〜1週間の計画期間について、各時間帯(期)に「どの注文グレードの溶湯を、何回(整数)、1回あたり何トン(連続)溶かし、その各チャージにスクラップ在庫のどのロットを何トン投入するか」を決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/foundry_charge_mix_multiperiod.py) |
| ⭐ **petroleum_pooling** ([学習notebook](../notebooks/samples/petroleum_pooling.ipynb)) | 石油調達→プーリング→製品ブレンドの多期計画 (Multi-period Petroleum Pooling). — 中堅の石油精製・調達会社の「調達計画部」が、数週間の計画期間について、どの原料(スイート/サワー原油・各種留分)を、いつ、どれだけ買い付け、どの中間タンク(プール)に入れ、そこからどの製品(プレミアム/レギュラー等)へブレンドするかを決める意思決定である。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/petroleum_pooling.py) |
| agribusiness_crop_mix | 農業法人の作付計画 (Agribusiness Crop Mix Planning) — 農業法人の営農計画担当者が、来季どの作物をどの圃場にどれだけ作付けするかを決める。作物ごとに単位面積あたりの利益・水使用量・労働時間が異なり、圃場ごとに利用可能面積が異なる(圃場1は灌漑設備あり、圃場2は天水のみ、など)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/agribusiness_crop_mix.py) |
| automotive_paint_shop | 自動車塗装順序・段取り最適化 (Automotive Paint Shop Sequencing) — 自動車組立工場の塗装工程管理者が、当直の生産スケジュール(タイムスロットごとにどの色を塗るか)を決める。同じ色を連続して流せば色替え(パージ・洗浄)が不要だが、色替えのたびに段取り時間とロス塗料のコストが発生するため、需要を満たしつつ色替え回数を最小化したい。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/automotive_paint_shop.py) |
| beverage_bottling_line | 飲料ボトリングライン段取り最適化 (Beverage Bottling Line Scheduling) — 飲料メーカーの生産計画担当者が、1本のボトリングラインで複数SKU(製品銘柄・容量違い)をどのシフトにどれだけ生産するかを決める。SKUを切り替えるたびに殺菌・充填ラインの洗浄(CIP)段取りが発生し稼働時間を圧迫するため、切替回数を抑えつつ各SKUの需要を満たす生産計画を立てる必要がある。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/beverage_bottling_line.py) |
| blending_mip | 配合設計問題(整数変数付き) (Blending Problem, MIP variant) — 飼料工場の配合(フォーミュレーション)担当者が、トウモロコシ・大豆粕・魚粉などの原材料を混ぜ合わせ、規定のタンパク質含有率・脂肪含有率を満たす配合飼料をロット生産する。各原材料は仕入先との取引条件により「使うなら最低ロット量以上」という最小購入量の縛りがあり、少量だけつまみ食い的に使うことはできない。栄養基準を満たしつつ、原材料費の合計を最小化する配合レシピを決める必要がある。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/blending_mip.py) |
| foundry_charge_mix | 鋳造チャージ配合設計（単期・複数注文の原料ブレンド） (Foundry Charge Mix) — 鋳物工場の溶解係が、1回のヒート(電気炉での溶解)について、手元の複数のスクラップロット(炭素・銅の含有率と在庫量が異なる)をどれだけ配合して溶かすか、整数のヒート回数と連続の1回あたり装入量を決める。溶けた1つの湯は複数の注文へ配分されるため、湯の成分(濃度)は配分先の全注文の規格窓を同時に満たす必要があり(濃度×配分量の双線形制約)、規格を満たせない分は割高な外部購入(規格適合材の外注)で補う。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/foundry_charge_mix.py) |
| lot_sizing | 多期間ロットサイジング問題 (Multi-period Lot Sizing Problem) — 消費財メーカーの生産計画担当者が、月次の需要予測をもとに1年間(12か月)の生産ロットサイズ(いつ・どれだけ生産するか)を決める。生産を開始するたびに段取り替え(設備の切り替え・治具交換)による固定費用が発生する一方、需要より多く作って在庫として持ち越すと保管コストがかかる。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/lot_sizing.py) |
| semiconductor_wafer_fab | 半導体ウェハ工場搬送スケジュール (Semiconductor Wafer Fab Routing) — 半導体製造ラインの「搬送システム管理者」が、ウェハキャリア(ロット)を各工程間で運ぶ自動搬送ロボット(OHT/AMR)への割当を決める意思決定である。各ロットはいずれか1台のロボットに割り当てなければならず、ロボットには同時搬送できるキャリア数の上限(積載容量)がある。ロボットごとに現在位置からロットの搬送元までの移動時間が異なるため、割当次第で搬送完了までの総所要時間が変わる。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/semiconductor_wafer_fab.py) |
| steel_continuous_casting | 鉄鋼連続鋳造製造スケジュール (Steel Continuous Casting Scheduling) — 製鉄所の「鋳造工程スケジューラ」が、複数の鋳造ライン(ストランド)上で連続鋳造される複数のヒート(溶鋼バッチ)の投入順序と開始時刻を決める意思決定である。連続鋳造はタンディッシュ(中間容器)を空にできないため、同一ラインの連続するヒート間には最小・最大の投入間隔(鋳造ギャップ)が業務上定められている(間隔が短すぎると凝固が追いつかず、長すぎるとタンディッシュ内の溶鋼が冷えて品質不良になる)。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/steel_continuous_casting.py) |

[← カタログ全体へ戻る](index.md)
