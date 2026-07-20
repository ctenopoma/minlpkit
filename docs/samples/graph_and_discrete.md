# グラフ・離散構造

彩色・被覆・分割・マッチングなど、グラフ/組合せ構造の離散最適化。対称性除去や集合分割の題材。

**11 本** / `scale` 引数対応 1 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| feature_selection | 特徴量選択によるスパース回帰 (MIP) — Feature Selection for Regression — 臨床データ分析チームのデータサイエンティストが、健診受診者の検査値(血圧・BMI・ | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/feature_selection.py) |
| frequency_assignment | 周波数割当問題 (MIP) — Frequency Assignment Problem — 移動体通信事業者の無線ネットワーク設計担当者が、市内に設置した基地局(セル) | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/frequency_assignment.py) |
| graph_coloring | グラフ彩色 (MILP) — 対称性除去の実証用 — 隣接頂点を異色で塗り、使う色数を最小化する。色は完全に入替可能なので | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/graph_coloring.py) |
| k_means_mip | K-meansクラスタリング (MIP定式化) — K-Means Clustering — 小売チェーンの物流企画担当者が、各店舗の所在地(座標)を基に、新設する配送 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/k_means_mip.py) |
| max_clique_mip | 最大クリーク問題 (MIP定式化) — Maximum Clique Problem — 人事部門のプロジェクトチーム編成担当者が、社員間の「過去プロジェクトでの | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/max_clique_mip.py) |
| optimal_decision_tree | 最適決定木 (簡略版MIP) — Optimal Decision Tree — 消費者金融の融資審査担当者が、申込者の属性(年収スコア・借入希望額スコア・ | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/optimal_decision_tree.py) |
| qap_linearized | 線形化二次割当問題 (QAP) — Linearized Quadratic Assignment Problem — 工場レイアウト設計担当者が、複数の生産設備(機械・工程)を工場内の候補設置場所に | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/qap_linearized.py) |
| set_cover | 集合被覆問題 (MIP) — Set Cover Problem — 市の消防局配置計画担当者が、市内15地区すべてを緊急対応カバー範囲に収める | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_cover.py) |
| set_partitioning | 大規模集合分割問題 (MILP) — GPU primal heuristics の検証用 — 乗務員ペアリング等の原型。要素全体をちょうど1回ずつ覆う列の組合せを費用最小で選ぶ。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_partitioning.py) |
| steiner_tree | シュタイナー木問題 (MIP) — Steiner Tree Problem in Graphs — 通信キャリアのネットワーク敷設担当者が、複数の拠点(データセンターや基地局など | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/steiner_tree.py) |
| sudoku_mip | 数独ソルバー (MIP定式化) — Sudoku Solver — パズル誌の編集担当者が、出題した9x9数独パズルに唯一解が存在するかを検証する | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/sudoku_mip.py) |

[← カタログ全体へ戻る](index.md)
