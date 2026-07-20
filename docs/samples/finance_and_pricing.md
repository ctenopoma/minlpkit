# 金融・価格設計

ポートフォリオ選択・価格付け・収益管理。リスク項(分散)や区分価格などの非線形・離散意思決定を含む。

**9 本** / `scale` 引数対応 5 本。 ⭐ は事業ストーリーが特に厚い旗艦サンプル。`scale` 列 ✓ は `build_model(scale=...)` で規模可変。

| サンプル | 事業ストーリー | scale | ソース |
| --- | --- | :---: | :---: |
| cash_flow_matching | Cash Flow Matching Problem. — Dedicates a portfolio of bonds to meet a schedule of liabilities. | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/cash_flow_matching.py) |
| credit_scoring_tree | 信用リスク評価の閾値分類 (Credit Scoring Threshold Optimization) — 消費者金融の与信審査部門が、申込者を「承認/謝絶」に振り分けるスコアカットオフを | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/credit_scoring_tree.py) |
| dynamic_pricing_hotel | ホテル客室の動的価格決定 (Dynamic Pricing for Hotel Rooms) — ホテルのレベニューマネージャーが、複数の部屋タイプ(スタンダード・スイート等)について | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/dynamic_pricing_hotel.py) |
| loan_portfolio_optimization | ローン与信ポートフォリオ利回り最大化 (Loan Portfolio Optimization). — 銀行の与信ポートフォリオ管理者が、複数の融資商品(住宅・消費者・中小企業向けなど) | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/loan_portfolio_optimization.py) |
| portfolio_cvar | 条件付き確実性価値 (CVaR) ポートフォリオ最適化 (Portfolio CVaR). — 資産運用担当者が、複数の資産クラス(株式・債券・オルタナティブなど)への | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/portfolio_cvar.py) |
| portfolio_mip | Portfolio Optimization with Cardinality Constraints (MIP). — Maximizes return (or minimizes risk) subject to a limit on the number… | — | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/portfolio_mip.py) |
| price_optimization_markdown | 小売シーズン値引き価格最適化 (Price Optimization with Markdown) — 小売チェーンの「プライシング担当」が、季節商品(アパレル等)の複数店舗・複数週にわたる | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/price_optimization_markdown.py) |
| r_and_d_project_portfolio | R&D新規事業投資ポートフォリオ (R&D Project Portfolio) — 研究開発部門の「R&D投資委員会」が、複数年度にわたる研究開発予算配分を決める意思決定 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/r_and_d_project_portfolio.py) |
| retail_markdown_clearance | 小売クリアランス値引き時期決定 (Retail Clearance Markdown) — 小売チェーンの「在庫消化担当」が、シーズン末在庫を持つ複数商品カテゴリについて、 | ✓ | [source](https://github.com/ctenopoma/minlpkit/blob/main/samples/finance_and_pricing/retail_markdown_clearance.py) |

[← カタログ全体へ戻る](index.md)
