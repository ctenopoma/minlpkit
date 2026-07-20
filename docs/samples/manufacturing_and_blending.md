# 製造・ブレンド

配合・プーリング・鋳造チャージ。濃度×流量の双線形(プーリング)を核とするプロセス産業のバッチ/多期モデル群。

**10 本**(うち旗艦 ⭐ 2 本) / `scale` 引数対応 2 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| ⭐ **foundry_charge_mix_multiperiod** | 鋳造の多期チャージ配合計画 (Multi-period Foundry Charge Mix). — 電気炉(EAF)を持つ鋳物工場の「溶解計画係」が、数日〜1週間の計画期間について、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/foundry_charge_mix_multiperiod.py) |
| ⭐ **petroleum_pooling** | 石油調達→プーリング→製品ブレンドの多期計画 (Multi-period Petroleum Pooling). — 中堅の石油精製・調達会社の「調達計画部」が、数週間の計画期間について、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/petroleum_pooling.py) |
| agribusiness_crop_mix | 農業作物ミックス計画 (Agribusiness Crop Mix Planning) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/agribusiness_crop_mix.py) |
| automotive_paint_shop | 自動車塗装順序最適化 (Automotive Paint Shop Sequencing) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/automotive_paint_shop.py) |
| beverage_bottling_line | 飲料ボトリング段取り最適化 (Beverage Bottling Line Scheduling) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/beverage_bottling_line.py) |
| blending_mip | Blending Problem (MIP variant) — This model determines the optimal blend of raw materials to produce a final product. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/blending_mip.py) |
| foundry_charge_mix | 鋳造配合設計（原料ブレンド） (Foundry Charge Mix) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/foundry_charge_mix.py) |
| lot_sizing | Multi-period Lot Sizing Problem — This model minimizes the total cost of production, setup, and inventory holding | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/lot_sizing.py) |
| semiconductor_wafer_fab | 半導体ウェハ工場搬送スケジュール (Semiconductor Wafer Fab Routing) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/semiconductor_wafer_fab.py) |
| steel_continuous_casting | 鉄鋼連続鋳造製造スケジュール (Steel Continuous Casting Scheduling) — 実務問題ベースの数理最適化サンプルモデルです。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/manufacturing_and_blending/steel_continuous_casting.py) |

[← カタログ全体へ戻る](index.md)
