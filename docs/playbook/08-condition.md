# 8. 条件数・数値健全性

[← プレイブック目次](index.md)

### こんな課題ありませんか

- 求解結果が実行環境やSCIPバージョンで微妙に違う、あるいは「怪しい」数値が出る。
- 「係数のオーダーが揃っていない気がする」がどのくらい問題なのか判断がつかない。

### 診断で何がわかるか

`numerical_scale`(warning、[3. Big-M排除](03-bigm.md)と共通)は presolve後の残存係数比
(`residual_coef_ratio ≥ 1e6`)を見る。ただしこれは max/min 比であり、**真の条件数の代用には
ならない**(下記参照)。

### 打ち手の仕組み

係数の max/min 比は「レンジの広さ」を見るだけで、行列の悪条件性(数値誤差の増幅度合い)の
正確な指標ではない。真の条件数 κ(A) は係数行列の特異値分解(SVD)の `σ_max/σ_min` で得る
(`matrix_condition`、solve前の定式化診断)。加えて、実際に解いたときの最適LP基底の条件数は
`scip_basis_condition`(SCIPの `getCondition()`)で別途測れる。前者は定式化そのものの
悪条件、後者は「実際に解いたときの基底の不安定度」を測るという意味で相補的。

### 効果(このリポジトリでの実測)

緩いBig-Mで κ(A)=3.5e4、tight化で κ(A)=32(**定式化の選び方が数値健全性を100倍以上左右する**)。
`unit_commitment` は LP基底 κ≈2.6e11 と極端で、実際に数値不安定リスクがある領域
(FINDINGS §3b、[`condition.html`](../gallery/condition.html))。

### 効かないとき・注意

- 係数の max/min 比だけで「数値問題あり」と早合点しないこと。自然なコスト差(~1e3程度)は
  数値問題ではなく、真の悪条件は presolve後で1e6以上のレンジと見るべき(FINDINGS §1)。
- 条件数を改善する具体的な打ち手は多くの場合「Big-M排除」([3. Big-M排除](03-bigm.md))や
  「変数境界のタイト化」であり、条件数診断そのものは**症状を数値化する道具**であって、
  それ単体で解決策にはならない。

### 使い方

```python
from minlpkit.collectors.static_diag import matrix_condition, scip_basis_condition

kappa_static = matrix_condition(build_model())      # solve前、SVDベース
m = build_model(); m.optimize()
kappa_basis = scip_basis_condition(m)                # solve後、SCIP LP基底
```

Worked example: `experiments/run_condition.py` → [`condition.html`](../gallery/condition.html)。
