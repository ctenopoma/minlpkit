# 1. 整数×連続の厳密線形化

[← 手法ガイド目次](index.md)

### こんな課題ありませんか

- 「整数個 × 連続量」(バッチ数×サイズ、台数×稼働時間、など)の積が制約に出てくる。
- SCIP が McCormick 緩和で解いてくれるはずなのに gap が全然縮まらない。
- 診断が `weak_relaxation`(serious)を出し、evidence に自分の書いた双線形項が挙がっている。

### 診断で何がわかるか

`weak_relaxation` は「特定の非線形制約に緩和違反が集中し(`bottleneck_rel_viol ≥ 0.5`)、かつ
空間分枝の寄与が大きい(`spatial_share ≥ 0.3`)」ときに発火する。evidence に
ボトルネック制約名と相対違反、空間分枝の寄与率が出る。`wide_term_range` は同じ症状の前兆
(区間演算で見た値域が広い)として先に出ることもある。

### 打ち手の仕組み

SCIP は「整数 $y$ × 連続 $x$」の積 $w = yx$ を、一般の双線形項と同じく **McCormick 緩和**
(4本の線形不等式で囲む凸包近似)で扱う。

$$
\begin{aligned}
w &\ge \underline{y}x + y\underline{x} - \underline{y}\,\underline{x}, &
w &\ge \overline{y}x + y\overline{x} - \overline{y}\,\overline{x},\\
w &\le \overline{y}x + y\underline{x} - \overline{y}\,\underline{x}, &
w &\le \underline{y}x + y\overline{x} - \underline{y}\,\overline{x}.
\end{aligned}
$$

しかし $y$ が整数なら、とりうる値 $v \in \{\underline{y},\dots,\overline{y}\}$ ごとに
指示変数 $\delta_v$($y=v$ のとき1)を置き、$x$ を分解すれば**緩和ギャップ0**で厳密に
線形表現できる。

$$
\sum_v \delta_v = 1,\quad
y = \sum_v v\,\delta_v,\quad
x = \sum_v x_v,\quad
w = \sum_v v\,x_v,\quad
0 \le x_v \le \overline{x}\,\delta_v .
$$

$y$ の値域が小さいほど補助変数が少なく効率的。「$y$ が整数」という情報を McCormick は
捨てているが、この分解は使い切る、というのが直感。

### 効果(このリポジトリでの実測)

`scheduling_plant`(バッチ数n×バッチサイズsの三重積 n·s·(T-T0))に適用:
**ルート双対境界 52→125(+140%)、25秒求解の gap 127%→49%、ノード数 7578→3840**、
最適値は不変([`improve_linearize.html`](../gallery/improve_linearize.html)、FINDINGS §3)。
汎用ヘルパー化後の横展開実証では、plant で +156%(52→133)、易しい `scheduling` では
+1%(132→133、元々易しいので伸び代が小さい)。

![厳密線形化の before/after: ルート双対境界・最終gap・ノード数](../assets/playbook/01-linearize-effect.png)

原理(McCormick 包絡線のギャップ)から効果測定までを図付きで追うには
[整数×連続の厳密線形化](../notebooks/improve/01_linearize_product.ipynb) を参照。

### 効かないとき・注意

- **y(整数側)の値域が広いと補助変数・制約が線形に増える**。バッチ数×バッチサイズのように
  整数側の値域が小さい積に向く。
- 「積が双線形だから」といって闇雲に有効不等式を足すのは逆効果。`n·s ≥ demand` を素朴に
  足すと n·s 自体が双線形なので**新たな非凸制約の追加**になり、ルート双対境界は
  **52.13→50.48 に悪化**する(FINDINGS §2)。「線形化してから」制約を足すのと、
  「双線形のまま」制約を足すのとでは効果が逆転する。
- 効くのは「非凸緩和の弱さが律速」のケース限定。[診断ベンチマーク](../census.md)では非線形11本中
  `weak_relaxation` 発火は1本のみで、多くのモデルでは出番がない(効果は問題依存)。

### 使い方

```python
import minlpkit as mk

ns = mk.linearize_product(m, n, s, y_lb=1, y_ub=3, x_lb=0.0, x_ub=10.0, name="ns")
m.addCons(ns >= 12)   # n*s >= 12 が厳密線形制約になる
```

API: [`mk.linearize_product`](../api/transforms.md)。
Worked example: `samples/others/scheduling_plant.py`(`linearize_ns=True`)、
`experiments/run_improve_linearize.py` → [`improve_linearize.html`](../gallery/improve_linearize.html)。
