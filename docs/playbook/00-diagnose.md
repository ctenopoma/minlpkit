# 0. 診断そのもの(analyze/findings/recipe)

[← プレイブック目次](index.md)

### こんな課題ありませんか

- モデルは書けたが、gap が縮まらない理由が SCIP のログを見てもわからない。
- 「何か改善しないといけない気がするが、どこから手を付ければいいかわからない」。
- 改善を試したが本当に効いたのか自信が持てない(体感で「たぶん速くなった」で終わる)。

### 診断で何がわかるか

`mk.analyze(build_fn, name, time_limit)` が、求解の裏側で以下を自動収集して `Report` を返す:

- 動的: 双対境界の帰属(どの分枝が効いたか)・停滞区間・空間分枝の比率・ノード数・可行解数・TTFF
- 非線形制約の違反(緩和解での「どの制約が一番破れているか」)
- 静的: 係数スケール(presolve前/後)・Big-M候補・制約-変数のブロック構造(結合制約)
- 対称性(入替可能な変数群)

これらの観測量(`report.metrics`)に、7つの診断ルール(`minlpkit/collectors/diagnose.py`)を
機械的に当てて発火した症状を `report.findings` に返す。各 finding は
`symptom`(症状)/ `cause`(疑われる原因)/ `recommendation`(推薦)/ `evidence`(実測値)/
`recipe`(**使う mk 関数 + worked example**)/ `severity`(good/warning/serious/critical)
を持つ。`recipe` があるので「症状 → どのページを読めばいいか」が直結する。

診断ルールの全表は [利用マニュアル: ワークフロー §診断ルール一覧](../manual/workflow.md#rules) を参照。

### 打ち手の仕組み

`analyze` 自体は「打ち手」ではなく「次に読むページを教えてくれる入口」。仕組みは単純な
閾値ルールで(「非線形制約の相対違反≥0.5 かつ空間分枝比率≥0.3 なら `weak_relaxation`」等)、
Optuna や ML のような重い判定ではない。閾値はすべてこのリポジトリの実測(FINDINGS.md)から
決めている。presolve**前**でなく presolve**後**の残存値で判断するのが要点で(例:
`residual_coef_ratio`)、これにより「SCIPが自動で締めるので発火させるべきでない」症状を
誤検出しない設計になっている(FINDINGS §1・診断センサス参照)。

### 効果(このリポジトリでの実測)

診断センサス(`experiments/run_census.py`)で4カテゴリ約50本に一括適用した結果
([診断センサス](../census.md)):

- 解析成功46本のうち残存gap>0.1%はわずか6本。現代SCIPの大半は瞬時に最適化する。
- 最も多く発火したのは `symmetry_info`(23本)・`decomposable`(9本)という **good(対応不要)**
  の情報系。「教科書的改善はSCIPが自動処理」という結論と整合する。
- 重大症状 `weak_relaxation` が発火したのは非線形11本中1本(`district_heating_detailed_physics`)
  のみ。非凸緩和の弱さが本当に律速になるケースは希少で、だからこそ見つけたら効く
  ([ハンズオン(1)](../notebooks/hands_on_diagnosis.ipynb)で深掘り)。

### 効かないとき・注意

- 診断は「症状の検出」であって「自動修正」ではない。完全自動改善は原理的に不可能
  (build 済みモデルから「どの積を線形化すべきか」を機械的に検出することはできない)。
  recipe が示す mk 関数を実際に自分で当てはめる必要がある。
- `dual_stall` や `wide_term_range` は「症状はある」ことしか教えない。効果があるかは
  必ず `mk.compare_variants` で before/after 検証すること(下の各ページ参照)。

### 使い方

```python
import minlpkit as mk

report = mk.analyze(build_model, name="my_model", time_limit=20)
print(report.summary())
for f in report.findings:
    print(f["severity"], f["symptom"], "->", f["recipe"])
report.dashboard("results/report_my_model.html")
```

API: [`mk.analyze`](../api/pipeline.md) / [`mk.evaluate` と診断ルール](../api/diagnose.md)。
Worked example: `demo.py`、`experiments/run_diagnose.py` →
[`report_plant.html`](../gallery/report_plant.html) / [`diagnose_plant.html`](../gallery/diagnose_plant.html)。
