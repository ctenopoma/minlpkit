# 金融・価格設計

ポートフォリオ選択・価格付け・収益管理。リスク項(分散)や区分価格などの非線形・離散意思決定を含む。

**9 本** / `scale` 引数対応 5 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| cash_flow_matching | キャッシュフローマッチング債券選択問題 (Cash Flow Matching Problem) — 年金基金や保険会社の資産運用担当者が、将来の年限ごとに確定している負債支払い(年金給付・保険金支払いなど)を、手持ちの候補債券群(利付債)への投資でどう「専用化(デディケーション)」するかを決める問題である。各債券は満期までの各期にクーポン(利息)と、満期時には元本を支払う。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/cash_flow_matching.py) |
| credit_scoring_tree | 信用リスク評価の閾値分類 (Credit Scoring Threshold Optimization) — 消費者金融の与信審査部門が、申込者を「承認/謝絶」に振り分けるスコアカットオフを決める。カットオフを下げれば承認件数(=金利収入)は増えるが、デフォルト(貸倒れ)リスクの高い申込者まで承認してしまう。年齢層(若年層/シニア層)でリスク特性が異なるため、セグメントごとに別々のカットオフを最適化する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/credit_scoring_tree.py) |
| dynamic_pricing_hotel | ホテル客室の動的価格決定 (Dynamic Pricing for Hotel Rooms) — ホテルのレベニューマネージャーが、複数の部屋タイプ(スタンダード・スイート等)について曜日区分(平日・週末・繁忙日)ごとの販売価格を決める。価格を上げれば単価は上がるが価格弾力的な需要曲線に沿って予約数は減るため、収益(価格×需要)は価格の非線形(二次)関数になる。客室在庫という物理的な容量制約に加え、週末・繁忙日は平日より高い価格設定にするというレベニューマネジメントの業務ルール(価格の順序制約)を反映する。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/dynamic_pricing_hotel.py) |
| loan_portfolio_optimization | ローン与信ポートフォリオ利回り最大化 (Loan Portfolio Optimization). — 銀行の与信ポートフォリオ管理者が、複数の融資商品(住宅・消費者・中小企業向けなど) | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/loan_portfolio_optimization.py) |
| portfolio_cvar | 条件付き確実性価値 (CVaR) ポートフォリオ最適化 (Portfolio CVaR). — 資産運用担当者が、複数の資産クラス(株式・債券・オルタナティブなど)への | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/portfolio_cvar.py) |
| portfolio_mip | カーディナリティ制約付きポートフォリオ最適化 (Portfolio Optimization with Cardinality Constraints) — 資産運用会社のポートフォリオマネージャーが、複数の候補銘柄(株式・債券・REIT等)の中から、実際に管理・監視できる銘柄数の上限(カーディナリティ)を守りながら、期待リターンを最大化する投資配分を決める問題である。 | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/portfolio_mip.py) |
| price_optimization_markdown | 小売シーズン値引き価格最適化 (Price Optimization with Markdown) — 小売チェーンの「プライシング担当」が、季節商品(アパレル等)の複数店舗・複数週にわたる値引き価格を決める意思決定である。各週の需要は価格弾力性(価格が下がるほど需要が増える線形近似)に従うため、売上 = 価格×需要 は価格の二次関数(非線形)になる。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/price_optimization_markdown.py) |
| r_and_d_project_portfolio | R&D新規事業投資ポートフォリオ (R&D Project Portfolio) — 研究開発部門の「R&D投資委員会」が、複数年度にわたる研究開発予算配分を決める意思決定である。各プロジェクトは複数年度(フェーズ)にわたって段階的に投資が必要で、年度ごとの予算上限を超えてはならない。また一部プロジェクトは技術的な前提関係(先行研究への投資が完了していないと後続フェーズに着手できない)を持つ。委員会は、限られた年度予算の下で採択するプロジェクト群(0/1の採否判断)を決め、期待リターンの合計を最大化する。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/r_and_d_project_portfolio.py) |
| retail_markdown_clearance | 小売クリアランス値引き時期決定 (Retail Clearance Markdown) — 小売チェーンの「在庫消化担当」が、シーズン末在庫を持つ複数商品カテゴリについて、数週間の販売期間中いつ・どれだけ値引き幅を投入するかを決める意思決定である。値引きは深いほど需要が伸びるがマージンを圧迫し、かつ一度値引きを開始したカテゴリは翌週以降も値引き幅を維持または拡大する(値引き幅を戻すと顧客の信頼を損なうため)という現場の運用ルールがある。 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/retail_markdown_clearance.py) |

[← カタログ全体へ戻る](index.md)
