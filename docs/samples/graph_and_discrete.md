# グラフ・離散構造

彩色・被覆・分割・マッチングなど、グラフ/組合せ構造の離散最適化。対称性除去や集合分割の題材。

**11 本** / `scale` 引数対応 1 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| feature_selection | Feature Selection for Regression (MIP). — Selects a subset of features to minimize regression error with a constraint on the numbe… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/feature_selection.py) |
| frequency_assignment | Frequency Assignment Problem. — Assigns frequencies to communication links such that interference is minimized or avoided. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/frequency_assignment.py) |
| graph_coloring | グラフ彩色 (MILP) — 対称性除去の実証用 — 隣接頂点を異色で塗り、使う色数を最小化する。色は完全に入替可能なので | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/graph_coloring.py) |
| k_means_mip | K-Means Clustering (MIP Formulation) — This model represents the k-means clustering problem as a Mixed-Integer Programming (MIP) p… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/k_means_mip.py) |
| max_clique_mip | Maximum Clique Problem (MIP Formulation) — This model finds the largest complete subgraph (clique) in a given graph. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/max_clique_mip.py) |
| optimal_decision_tree | Optimal Decision Tree (Simplified MIP). — Constructs a decision tree of fixed depth to minimize classification error. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/optimal_decision_tree.py) |
| qap_linearized | Linearized Quadratic Assignment Problem (QAP) — Assigns facilities to locations to minimize flow * distance costs. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/qap_linearized.py) |
| set_cover | Set Cover Problem — This model selects a minimum number of sets such that all elements in the universe are covered. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_cover.py) |
| set_partitioning | 大規模集合分割問題 (MILP) — GPU primal heuristics の検証用 — 乗務員ペアリング等の原型。要素全体をちょうど1回ずつ覆う列の組合せを費用最小で選ぶ。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_partitioning.py) |
| steiner_tree | Steiner Tree Problem in Graphs. — Finds a minimum-weight tree connecting a designated set of terminal nodes. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/steiner_tree.py) |
| sudoku_mip | Sudoku Solver (MIP Formulation) — This model solves a 9x9 Sudoku puzzle using integer programming. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/sudoku_mip.py) |

[← カタログ全体へ戻る](index.md)
