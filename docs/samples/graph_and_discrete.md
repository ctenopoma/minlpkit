# グラフ・離散構造

彩色・被覆・分割・マッチングなど、グラフ/組合せ構造の離散最適化。対称性除去や集合分割の題材。

**11 本** / `scale` 引数対応 1 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| feature_selection | 特徴量選択によるスパース回帰 (MIP) — Feature Selection for Regression — 臨床データ分析チームのデータサイエンティストが、健診受診者の検査値(血圧・BMI・血糖値など10項目)から将来の健康リスクスコアを予測する回帰モデルを構築する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/feature_selection.py) |
| frequency_assignment | 周波数割当問題 (MIP) — Frequency Assignment Problem — 移動体通信事業者の無線ネットワーク設計担当者が、市内に設置した基地局(セル)それぞれに使用する周波数チャネルを割り当てる。近接して電波が干渉し合う基地局同士に同じ周波数を割り当てると通話品質が劣化するため、干渉が起きる基地局ペアには異なる周波数を割り当てつつ、使用する周波数番号の最大値(=確保すべき周波数帯域幅、ライセンス費用に直結)を最小化する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/frequency_assignment.py) |
| graph_coloring | グラフ彩色 (MILP) — 対称性除去の実証用 — 隣接頂点を異色で塗り、使う色数を最小化する。色は完全に入替可能なので | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/graph_coloring.py) |
| k_means_mip | K-meansクラスタリング (MIP定式化) — K-Means Clustering — 小売チェーンの物流企画担当者が、各店舗の所在地(座標)を基に、新設する配送センターをどの店舗に併設するか、また各店舗をどの配送センターの配送エリアに割り当てるかを同時に決定する。店舗-配送センター間の距離の二乗和を最小化することで、配送ルートの総移動距離・配送コストを抑える(配送センターは既存店舗のいずれかに併設する前提のk-medoids型のMIP定式化)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/k_means_mip.py) |
| max_clique_mip | 最大クリーク問題 (MIP定式化) — Maximum Clique Problem — 人事部門のプロジェクトチーム編成担当者が、社員間の「過去プロジェクトでの協業実績あり(相性が良い)」関係を表すグラフから、全員同士が互いに良好な関係にある最大のグループ(クリーク)を見つけ、新規プロジェクトのコアチーム候補として推薦する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/max_clique_mip.py) |
| optimal_decision_tree | 最適決定木 (簡略版MIP) — Optimal Decision Tree — 消費者金融の融資審査担当者が、申込者の属性(年収スコア・借入希望額スコア・既存借入件数スコアの3指標)から「承認/却下」を判定する、深さ1の解釈可能な決定木ルールをMIPで学習する。複雑なブラックボックスモデルではなく「この指標がこの閾値を超えたら承認」という1本の分岐ルールに絞り込むことで、審査担当者や監督当局への説明責任を果たしつつ、過去16件の審査結果に対する誤判定を最小化する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/optimal_decision_tree.py) |
| qap_linearized | 線形化二次割当問題 (QAP) — Linearized Quadratic Assignment Problem — 工場レイアウト設計担当者が、複数の生産設備(機械・工程)を工場内の候補設置場所に割り当てる際、設備間で行き来する部材・仕掛品の物流量(フロー)と設置場所間の物理的な距離の積(=搬送コスト)の総和を最小化する。設備間フローと拠点間距離を同時に考慮する必要があるため目的関数が本質的に二次(割当変数の積)になり、Adams-Johnson法で線形化してMIPとして解く。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/qap_linearized.py) |
| set_cover | 集合被覆問題 (MIP) — Set Cover Problem — 市の消防局配置計画担当者が、市内15地区すべてを緊急対応カバー範囲に収めるために、候補となる消防署設置場所(候補地ごとにカバーできる地区の組合せが異なる)の中から最小限の署数を選んで開設する。開設・維持コストを抑えつつ、対応漏れの地区が出ないようにする。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_cover.py) |
| set_partitioning | 大規模集合分割問題 (MILP) — GPU primal heuristics の検証用 — 乗務員ペアリング等の原型。要素全体をちょうど1回ずつ覆う列の組合せを費用最小で選ぶ。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/set_partitioning.py) |
| steiner_tree | シュタイナー木問題 (MIP) — Steiner Tree Problem in Graphs — 通信キャリアのネットワーク敷設担当者が、複数の拠点(データセンターや基地局など必ず接続しなければならない「端点」)をすべて接続する光ファイバー網を、敷設コスト(距離・工事費)最小で設計する。端点以外の中継ノードを経由してもよいが、経由すること自体には追加コストが乗らず、実際に敷設した回線(エッジ)のコストのみがかかるため、端点だけを直接結ぶ木より安く済む場合がある(これがシュタイナー木問題)。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/steiner_tree.py) |
| sudoku_mip | 数独ソルバー (MIP定式化) — Sudoku Solver — パズル誌の編集担当者が、出題した9x9数独パズルに唯一解が存在するかを検証するため、整数計画法でパズルを解かせる。目的関数を持たない純粋な充足可能性問題(feasibility problem)として定式化し、与えられたヒント数字と数独のルール(行・列・3x3ブロックでの数字重複禁止)をすべて満たす解を1つ求める。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/graph_and_discrete/sudoku_mip.py) |

[← カタログ全体へ戻る](index.md)
