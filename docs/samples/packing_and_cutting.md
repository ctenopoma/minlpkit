# パッキング・カッティング

ナップサック・ビンパッキング・カッティングストック。列生成(Gilmore-Gomory)や被約コスト固定の実証台。

**9 本** / `scale` 引数対応 2 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| bin_packing_2d | 2D Bin Packing Problem — This model packs a set of rectangular items into the minimum number of identical rectangular bins. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/bin_packing_2d.py) |
| cutting_stock | カッティングストック問題 — 列生成の実証用 — 幅Wのロールから、幅w_iの品目を需要d_i本切り出す。使うロール本数を最小化。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/cutting_stock.py) |
| cutting_stock_advanced | カッティングストック問題 (アドバンスド) (Advanced Cutting Stock) — 標準的なカッティングストック問題に対し、実務上の制約である | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/cutting_stock_advanced.py) |
| gap_large | 大規模一般化割当問題 GAP (MILP) — GPU primal heuristics の検証用 — 各タスクをちょうど1エージェントに割り当て、容量制約下で費用最小化する。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/gap_large.py) |
| glass_cutting_2d | ガラス加工の定尺原板カット計画＋特注品寸法決定 (Glass Cutting 2D) — ガラス加工工場の生産管理担当者が、複数サイズの定尺原板(仕入先から2種類のサイズを購入可能) | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/glass_cutting_2d.py) |
| knapsack | 0-1 ナップサック (MILP) — 被約コスト固定の実証用 — 強相関(value_i ≈ weight_i + 定数)にすると LP緩和と整数最適のギャップが小さく、 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/knapsack.py) |
| mkp | Multidimensional Knapsack Problem (MKP) — This model maximizes the total value of items selected subject to multiple resource cons… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/mkp.py) |
| molded_parts_cutting | 射出成形型替え・製造スケジュール (Molded Parts Setup Optimization). — 射出成形工場の生産計画者が、複数種類の部品(金型)を複数期間(週次生産計画)に | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/molded_parts_cutting.py) |
| warehouse_slotting | 倉庫スロッティング配置最適化 (Warehouse Slotting Optimization) — 倉庫運営マネージャーが、複数のSKU(在庫管理単位)をピッキング効率の異なる複数のスロット | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/packing_and_cutting/warehouse_slotting.py) |

[← カタログ全体へ戻る](index.md)
