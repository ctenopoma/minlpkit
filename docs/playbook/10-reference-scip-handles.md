# 参考: SCIPが自動でやること

[← 手法ガイド目次](index.md)

このページの3手法は、教科書には載るが**現代の SCIP が既定で自動処理する**か、あるいは
**手を出すとかえって悪化する**ものである。「通常は対応不要」「常用非推奨」という結論を、
このリポジトリの実測(FINDINGS.md)とともに正直に示す。実装例は残すが、常用は推奨しない。

## 対称性除去(通常は対応不要) {: #symmetry}

### こんな課題ありませんか

- 同じコストの解が大量に出て、ノード数が爆発している気がする。
- 「機械が全部同じ性能」「品が入替可能」のような対称構造に心当たりがある。

### 診断で何がわかるか

`symmetry_info`(severity=**good**、つまり「情報」であり「推薦」ではない)が、
入替可能な変数群(1-hop color refinement で検出、全線形モデルのみ健全)を教えてくれる。

### 打ち手の仕組み(なぜ通常不要か)

教科書的な対策は「辞書式順序制約」(対称な変数群に順序を強制して片方だけ残す)。しかし
SCIP は `misc/usesymmetry`(既定ON)で対称性を自動検出・自動処理する。

### 効果(このリポジトリでの実測)

`makespan`(並列機械)・`graph_coloring` で SCIP内蔵対称性 ON/OFF × 手動除去 ON/OFF の
**全4通りが1ノードで解ける**(FINDINGS §1)。手動の辞書式除去を明示的に足すと、makespan では
ノード数が **1→24 に悪化する**(FINDINGS §2)。LP実行可能域を非対称に切って重くするため。

### 効かないとき・注意

- **手動除去は基本的に不要、むしろ悪化しうる**。`usesymmetry` を意図的にOFFにする特殊な
  運用でだけ辞書式除去が有効(通常はやらない)。
- 対称性検出自体は非線形制約があると偽陽性を起こしうるため、`sym_sound=False` のモデル
  (非線形入り)では診断は発火しない設計になっている。

### 使い方

診断が発火した場合の実装例のみ参照(常用は非推奨):
`experiments/run_symmetry.py` → [`symmetry.html`](../gallery/symmetry.html)。

---

## 被約コスト固定(SCIP既定で十分) {: #redcost}

### こんな課題ありませんか

- 変数が大量にあり、最適解では多くが0になっている(「列が過剰」に見える)。
- 「探索後半になっても問題サイズが縮まらない」。

### 診断で何がわかるか

専用の diagnose finding はない。列過多の兆候は `decomposable`(ブロック構造)や
モデル規模そのものから判断する。

### 打ち手の仕組み

被約コスト r_j が「主問題下界と現在の上界の差」を超える変数は最適解に入り得ないので
固定できる、という古典的な手法。

### 効果(このリポジトリでの実測)

SCIP は `propagating/redcost`(既定ON)でこれを自動実施する。`knapsack`(強相関45品)では
既定SCIPが**0ノード**で解く。効果を切り離すため素の分枝限定で比較すると、redcost ON 107
ノード / OFF 204 ノード(**−48%**)と技術自体は有効だが、SCIPが既に提供している
(FINDINGS §1、[`improve_redcost.html`](../gallery/improve_redcost.html))。

### 効かないとき・注意

- **手動再実装は冗長**。診断としても「手動実装が必要」ではなく「SCIP既定で有効」として扱う。
- 列が本当に指数的で列挙すら不能な規模になったら、これは被約コスト固定の話ではなく
  [6. 列生成](06-column-generation.md) の話になる。

### 使い方

参考実装のみ: `experiments/run_improve_redcost.py` →
[`improve_redcost.html`](../gallery/improve_redcost.html)(ON/OFF比較で技術の有効性を確認する
ためのコード)。実運用では何もしなくてよい。

---

## Perspective再定式化(常用非推奨) {: #perspective}

### こんな課題ありませんか

- on/off バイナリ×半連続な二次費用($fc \ge au + bp + cp^2$、$u=0$ なら $p=0$)を持つモデルの
  緩和を締めたい、と文献で見た「perspective化」を検討している。

### 診断で何がわかるか

専用の finding はない。`dual_stall` の一般的な推薦の中に理論上の選択肢として位置づけられる
が、下記の理由で minlpkit は積極的には推薦しない。

### 打ち手の仕組み

二次項だけを perspective 化した

$$
fc \ge au + bp + \frac{cp^2}{u}
\quad\Longleftrightarrow\quad
cp^2 \le (fc - au - bp)\,u
$$

は理論上凸包を締める再定式化で、右辺の形なら一般非線形制約として書き下せる。

### 効果(このリポジトリでの実測、負の結果)

Unit Commitment(on/off × 二次費用)に適用したところ、**既定SCIPではルート双対境界
117067.24→117067.71(+0.0004%、実質不変)**。presolve/分離がbaselineの凸二次を自動で
締めてしまうため。素の分枝限定(presolve/分離/対称性OFF)で比較すると
**113956→57784(−49%悪化)**(FINDINGS §1・§2、[`perspective.html`](../gallery/perspective.html))。

### 効かないとき・注意

- **理由**: SCIP は perspective 制約右辺の双線形項($fc\,u$, $u^2$, $p\,u$)を McCormick で
  緩く緩和してしまい、perspective本来の凸包(rotated SOC相当)の恩恵を活かせない。
  「双線形の新規追加」という意味で [1. 厳密線形化](01-linearize.md) の
  $n \cdot s \ge \text{demand}$ の逆効果と同型の失敗パターン。
- 等価変換なので最適値自体は不変(縮小4期での実測で32224.44=32224.44と一致)。
- **結論: SCIPに対しては素の凸二次下界の方が有利**。`mk.perspective_quadratic` は
  横展開可能な部品として提供するが、通常は使わない方がよい。

### 使い方(あえて使う場合)

```python
import minlpkit as mk

mk.perspective_quadratic(m, u, p, fc, a=1.0, b=2.0, c=0.5, name="persp")
```

API: [`mk.perspective_quadratic`](../api/transforms.md)(docstring に Warning あり)。
Worked example: `experiments/run_perspective.py` → [`perspective.html`](../gallery/perspective.html)。
