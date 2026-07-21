# Phase 16 バッチ4: 精緻化結果記録

対象: `samples/` 内10ファイル(finance_and_pricing / others / routing_and_logistics /
manufacturing_and_blending の一部)。定型docstring + 2-4変数純LPのトイを、業務ストーリーを
明示したdocstringと、複数期・複数拠点・整数決定・自然な非線形結合のいずれかを足した
モデルに拡張した。変数・制約数は `build_model("small")` 時点(SCIP presolve前)の値。

| ファイル | 変数(前→後) | 制約(前→後) | 新docstring要約 | 動作確認 |
| --- | --- | --- | --- | --- |
| finance_and_pricing/price_optimization_markdown.py | 3 → 22 | 2 → 24 | 複数店舗×複数週の値引き価格を、需要曲線(価格弾力性)と値下げ単調性(値上げ復帰禁止)の下で収益最大化 | optimal (small) |
| finance_and_pricing/r_and_d_project_portfolio.py | 4 → 5 | 1 → 5 | R&D投資委員会が複数年度予算・技術的前提関係(先行プロジェクト依存)の下でプロジェクト採否を決定 | optimal (small) |
| others/railway_line_planning.py | 2 → 6 | 1 → 7 | 運行計画部門が系統×列車種別ごとの運行頻度を、区間別線路容量と車両基地の編成数上限の下で収益最大化 | optimal (small) |
| finance_and_pricing/retail_markdown_clearance.py | 3 → 24 | 1 → 26 | 在庫消化担当が複数カテゴリ×複数週の値引きレベル(段階選択)を、在庫制約・クリアランス目標・戻し値引き禁止の下で粗利損失最小化 | optimal (small, default とも確認) |
| routing_and_logistics/ride_hailing_matching.py | 4 → 16 | 4 → 12 | ディスパッチが複数ドライバー×複数乗客の一対一マッチングを、距離ベース価値・優先度・シフト走行距離上限の下で最大化 | optimal (small) |
| manufacturing_and_blending/semiconductor_wafer_fab.py | 4 → 18 | 2 → 11 | 搬送システム管理者がロット×ロボットの割当を、積載容量・優先ロットの搬送時間上限の下で総搬送時間最小化 | optimal (small) |
| others/smart_home_appliances.py | 6 → 18 | 2 → 10 | HEMSが複数家電の稼働時間帯を、契約ブレーカー容量・稼働完了希望期限の下で電気代最小化 | optimal (small) |
| energy_and_microgrid/solar_pv_inverter.py | 2 → 18 | 1 → 21 | 系統連系運用者が複数インバータ×複数時間帯の有効/無効電力配分を、皮相電力の円形容量制約(非線形)と系統無効電力要求の下で売電収益最大化 | optimal (small) |
| manufacturing_and_blending/steel_continuous_casting.py | 3 → 19 | 4 → 44 | 鋳造工程スケジューラが複数ヒート×複数ラインの投入順序を、鋳造ギャップ制約(disjunctive、Big-M)と鋼種切替段取りの下でメイクスパン最小化 | optimal (small) |
| routing_and_logistics/supply_chain_multi_commodity.py | 2 → 12 | 3 → 12 | サプライチェーン計画担当が複数品目×複数拠点間の輸送配分とリンク開設可否を、能力・需要充足制約の下で総コスト最小化 | optimal (small) |

## 補足(非自明な事実)

- `retail_markdown_clearance.py`: 目的関数を `sold * margin_loss` の双線形(連続変数×バイナリ)
  で組むと SCIP が `ValueError: SCIP does not support nonlinear objective functions` を出す。
  `sold` 自体が `level_sel`(バイナリ)の線形結合で定義されているため、係数を事前展開して
  `level_sel` のみの線形式に書き直すことで回避した(双線形項を作らない)。
- 同ファイル: 在庫上限を固定値にすると、値引きなし(baseline)の週次需要合計だけで在庫上限を
  超えてしまい `presolving detected infeasibility` になるケースがあった。在庫を
  `n_week * base_demand[c] * 1.15` という需要ベースの式に変更し、baselineでも在庫超過せず
  かつクリアランス目標(在庫の85%)も達成可能な範囲に収めた。

## 実行コマンド

```
$env:PYTHONIOENCODING='utf-8'
uv run python samples/finance_and_pricing/price_optimization_markdown.py 2>$null
# ... (他9本も同様)
```

10本すべて `status: optimal`(`build_model("small")` にて)を確認済み。
