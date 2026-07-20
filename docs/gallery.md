# 成果ギャラリー

`minlpkit` の各機能(可視化・診断・改善の検証)を実際のサンプルモデルで動かした成果HTML集。
すべて `experiments/run_*.py` や `demo.py` の出力をそのまま埋め込んでいる(plotly.jsインライン、
実行結果込みの静的HTML)。★ は SCIP が自動ではやらない「真の価値がある改善」。

- 🖥️ **成果インデックス(元のホームページ)**: [gallery/index.html](gallery/index.html)

## 可視化

| ページ | 内容 |
| --- | --- |
| [収束モニタ(plant)](gallery/plant_dashboard.html) | primal/dual bound推移・gap対数・Primal Integral |
| [収束モニタ(UC)](gallery/uc_dashboard.html) | Unit Commitmentの求解トラジェクトリ |
| [McCormick凸緩和](gallery/mccormick.html) | 双線形項の緩和が区間分割で締まる3Dアニメ |
| [空間分枝木](gallery/tree.html) | 分枝変数の型(空間/整数/0-1)で色分け |
| [gap停滞と効いた分枝](gallery/attribution.html) | 双対境界改善の分枝への帰属 |
| [非線形制約の違反量](gallery/violation.html) | ルート緩和のボトルネック制約ヒートマップ |
| [スラック/IIS](gallery/bottleneck.html) | 線形制約の拘束・IIS(削除フィルタ法) |
| [静的診断(plant)](gallery/static_plant.html) | 係数スケール・ブロック構造・結合制約 |
| [静的診断(UC)](gallery/static_uc.html) | Big-M検出・悪条件制約 |
| [区間演算の値域](gallery/interval.html) | 非線形項の値域から緩和の緩さを静的予測 |
| [対称性検出](gallery/symmetry.html) | 入替可能な変数群(color refinement) |

## 診断(SCIP-aware)

| ページ | 内容 |
| --- | --- |
| [minlpkit レポート(plant)](gallery/report_plant.html) | `analyze()` 統合レポート: 観測量+推薦 |
| [診断(plant)](gallery/diagnose_plant.html) | 症状→原因→推薦→根拠 |
| [診断(UC)](gallery/diagnose_uc.html) | 残存Big-Mの検出 |
| [診断(並列機械)](gallery/diagnose_parallel.html) | 対称性=SCIP自動処理(情報) |
| [診断(施設配置)](gallery/diagnose_facility.html) | 症状なし(健全) |

## 改善の実施と効果検証

| ページ | 内容 |
| --- | --- |
| [n·s厳密線形化 ★](gallery/improve_linearize.html) | SCIPがやらない真の改善: ルート境界+140% |
| [列生成(GG) ★](gallery/colgen.html) | 指数的な列を暗黙に扱う(131中13で最適LP) |
| [Optunaチューニング](gallery/tune.html) | 問題クラス特化で双対境界+6.6% |
| [Big-M排除](gallery/improve_bigm.html) | LP緩和+347%(presolveが補償) |
| [被約コスト固定](gallery/improve_redcost.html) | SCIP提供。素B&Bで−48% |
| [ベンダーズ分解 ★](gallery/benders.html) | 主/サブ分解が単一問題の最適値に収束(3反復) |
| [条件数 κ(A) 診断](gallery/condition.html) | Model Analyzer核心。UC基底κ=2.6e11を検出 |
| [列生成の双対安定化 ★](gallery/stabilize.html) | Wentges smoothing で反復−19%(tailing-off抑制) |
| [SOS2 区分線形近似](gallery/sos.html) | Big-M回避。バイナリ0個 vs Big-M版20個 |
| [branch-and-price ★](gallery/bnp.html) | 汎用ドライバで整数最適24ロール(最適性証明) |
| [Perspective再定式化](gallery/perspective.html) | 負の結果: 既定で不変・素だと−49%(SCIPがMcCormickで緩む) |

---

★ = SCIP が自動ではやらない「真の価値がある改善」。その他は SCIP 内蔵機能の再確認や、
presolve が補償する定式化差。ライブモニタで自分のモデルを動かす場合は
`uv run python -m minlpkit.live.server` を参照([利用マニュアル: ライブモニタ](manual/live-monitor.md))。
