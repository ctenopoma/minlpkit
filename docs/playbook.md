# プレイブック — 症状から打ち手へ

**「モデリングはできる(PySCIPOptで定式化を書ける)が、列生成・ベンダーズ・再定式化などの
手法を知らない実務者」**を読者に想定したガイド。「自分は何に困っているのか → 何がわかるのか
→ 打ち手はどういう仕組みか → どのくらい効くのか」を、このリポジトリで**実際に測った数値**
だけを根拠に辿れるようにする。

> 前提として繰り返す minlpkit の設計思想: **現代の SCIP は教科書的改善の多くを presolve /
> 分離 / 対称性処理 / 被約コスト固定で自動解消する**。ここに載っている打ち手は、SCIP が
> 自動ではやらないもの(非凸緩和の弱さを突く定式化の作り込み・分解アルゴリズム)を中心に、
> 「SCIPは自動でやる、手を出す価値は薄い」ものも正直に含めている。

## 症状 → ジャンプ表

まず自分が困っていることに近いものを選ぶ。

| こんな症状 | 読む節 |
| --- | --- |
| そもそも診断って何をしてくれるのか知りたい | [0. 診断そのもの](#0-analyzefindingsrecipe) |
| gap が縮まらない / dual bound が停滞する | [3. 整数×連続の厳密線形化](#3-integer-x-continuous-linearization) / [7. ベンダーズ分解](#7-benders) / [8. 列生成](#8-column-generation) |
| 非線形項(べき乗・非凸関数)の近似が粗い、SOSやBig-Mで迷っている | [4. PWL近似(SOS2)](#4-pwl-sos2) / [5. Big-M排除](#5-bigm) |
| モデルが巨大になって作れない/列挙できない(パターン数が指数的) | [8. 列生成](#8-column-generation) |
| 解くたびに結果が違う/数値が怪しい(丸め誤差・不安定な基底) | [10. 条件数・数値健全性](#10-condition) |
| 可行解が全然見つからない(大規模0-1問題) | [9. GPU warm start](#9-gpu) |
| パラメータをどう選べばいいかわからない | [6. SCIPパラメータチューニング](#6-tuning) |
| 求解の進み方を見ながら止めたい/後で追いたい/前回と同じ条件で再現したい | [11. ライブ監視・run記録・再現](#11-live) |
| ノード数が爆発する(対称な解が大量にある) | [1. 対称性除去](#1-symmetry)(結論: 通常は対応不要) |
| 変数が大量に0で「列が過剰」に見える | [2. 被約コスト固定](#2-redcost)(結論: SCIP既定で十分) / [8. 列生成](#8-column-generation) |
| 半連続な二次費用(on/off × 二次)を締めたい | [12. Perspective再定式化](#12-perspective)(結論: 常用非推奨) |

---

## 0. 診断そのもの(analyze/findings/recipe) {: #0-analyzefindingsrecipe}

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
を持つ。`recipe` があるので「症状 → どの節を読めばいいか」が直結する。

診断ルールの全表は [利用マニュアル §5](manual.md#5-rules) を参照。

### 打ち手の仕組み

`analyze` 自体は「打ち手」ではなく「次に読む節を教えてくれる入口」。仕組みは単純な
閾値ルールで(「非線形制約の相対違反≥0.5 かつ空間分枝比率≥0.3 なら `weak_relaxation`」等)、
Optuna や ML のような重い判定ではない。閾値はすべてこのリポジトリの実測(FINDINGS.md)から
決めている。presolve**前**でなく presolve**後**の残存値で判断するのが要点で(例:
`residual_coef_ratio`)、これにより「SCIPが自動で締めるので発火させるべきでない」症状を
誤検出しない設計になっている(FINDINGS §1・診断センサス参照)。

### 効果(このリポジトリでの実測)

診断センサス(`experiments/run_census.py`)で4カテゴリ約50本に一括適用した結果
([診断センサス](census.md)):

- 解析成功46本のうち残存gap>0.1%はわずか6本。現代SCIPの大半は瞬時に最適化する。
- 最も多く発火したのは `symmetry_info`(23本)・`decomposable`(9本)という **good(対応不要)**
  の情報系。「教科書的改善はSCIPが自動処理」という結論と整合する。
- 重大症状 `weak_relaxation` が発火したのは非線形11本中1本(`district_heating_detailed_physics`)
  のみ。非凸緩和の弱さが本当に律速になるケースは希少で、だからこそ見つけたら効く
  ([ハンズオン(1)](notebooks/hands_on_diagnosis.ipynb)で深掘り)。

### 効かないとき・注意

- 診断は「症状の検出」であって「自動修正」ではない。完全自動改善は原理的に不可能
  (build 済みモデルから「どの積を線形化すべきか」を機械的に検出することはできない)。
  recipe が示す mk 関数を実際に自分で当てはめる必要がある。
- `dual_stall` や `wide_term_range` は「症状はある」ことしか教えない。効果があるかは
  必ず `mk.compare_variants` で before/after 検証すること(下の各節参照)。

### 使い方

```python
import minlpkit as mk

report = mk.analyze(build_model, name="my_model", time_limit=20)
print(report.summary())
for f in report.findings:
    print(f["severity"], f["symptom"], "->", f["recipe"])
report.dashboard("results/report_my_model.html")
```

API: [`mk.analyze`](api/pipeline.md) / [`mk.evaluate` と診断ルール](api/diagnose.md)。
Worked example: `demo.py`、`experiments/run_diagnose.py` →
[`report_plant.html`](gallery/report_plant.html) / [`diagnose_plant.html`](gallery/diagnose_plant.html)。

---

## 1. 対称性除去(参考: SCIPが自動でやる) {: #1-symmetry}

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
**全4通りが1ノードで解けた**(FINDINGS §1)。手動の辞書式除去を明示的に足すと、makespan では
ノード数が **1→24 に悪化**した(FINDINGS §2)。LP実行可能域を非対称に切って重くするため。

### 効かないとき・注意

- **手動除去は基本的に不要、むしろ悪化しうる**。`usesymmetry` を意図的にOFFにする特殊な
  運用でだけ辞書式除去が有効(通常はやらない)。
- 対称性検出自体は非線形制約があると偽陽性を起こしうるため、`sym_sound=False` のモデル
  (非線形入り)では診断は発火しない設計になっている。

### 使い方

診断が発火した場合の実装例のみ参照(常用は非推奨):
`experiments/run_symmetry.py` → [`symmetry.html`](gallery/symmetry.html)。

---

## 2. 被約コスト固定(参考: SCIPが自動でやる) {: #2-redcost}

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
(FINDINGS §1、[`improve_redcost.html`](gallery/improve_redcost.html))。

### 効かないとき・注意

- **手動再実装は冗長**。診断としても「手動実装が必要」ではなく「SCIP既定で有効」として扱う。
- 列が本当に指数的で列挙すら不能な規模になったら、これは被約コスト固定の話ではなく
  [8. 列生成](#8-column-generation) の話になる。

### 使い方

参考実装のみ: `experiments/run_improve_redcost.py` →
[`improve_redcost.html`](gallery/improve_redcost.html)(ON/OFF比較で技術の有効性を確認する
ためのコード)。実運用では何もしなくてよい。

---

## 3. 整数×連続の厳密線形化 {: #3-integer-x-continuous-linearization}

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

SCIP は「整数 y × 連続 x」の積を、一般の双線形項と同じく **McCormick 緩和**(4本の線形不等式
で囲む凸包近似)で扱う。しかし y が整数だと、y のとりうる値ごとに指示変数 δ_v(y=v)を作り、
x を `x = Σ_v x_v` に分解して `w = Σ_v v·x_v` とすれば、y·x を**緩和ギャップ0**で厳密に
線形表現できる(y の値域が小さいほど補助変数が少なく効率的)。「y が整数」という情報を
McCormick は捨てているが、この分解は使い切る、というのが直感。

### 効果(このリポジトリでの実測)

`scheduling_plant`(バッチ数n×バッチサイズsの三重積 n·s·(T-T0))に適用:
**ルート双対境界 52→125(+140%)、25秒求解の gap 127%→49%、ノード数 7578→3840**、
最適値は不変([`improve_linearize.html`](gallery/improve_linearize.html)、FINDINGS §3)。
汎用ヘルパー化後の横展開実証では、plant で +156%(52→133)、易しい `scheduling` では
+1%(132→133、元々易しいので伸び代が小さい)。
[ハンズオン(2)](notebooks/hands_on_improvement.ipynb) で同じ実験を追える。

### 効かないとき・注意

- **y(整数側)の値域が広いと補助変数・制約が線形に増える**。バッチ数×バッチサイズのように
  整数側の値域が小さい積に向く。
- 「積が双線形だから」といって闇雲に有効不等式を足すのは逆効果。`n·s ≥ demand` を素朴に
  足すと n·s 自体が双線形なので**新たな非凸制約の追加**になり、ルート双対境界は
  **52.13→50.48 に悪化**した(FINDINGS §2)。「線形化してから」制約を足すのと、
  「双線形のまま」制約を足すのとでは効果が逆転する。
- 効くのは「非凸緩和の弱さが律速」のケース限定。診断センサスでは非線形11本中 `weak_relaxation`
  発火は1本のみで、多くのモデルでは出番がない(効果は問題依存)。

### 使い方

```python
import minlpkit as mk

ns = mk.linearize_product(m, n, s, y_lb=1, y_ub=3, x_lb=0.0, x_ub=10.0, name="ns")
m.addCons(ns >= 12)   # n*s >= 12 が厳密線形制約になる
```

API: [`mk.linearize_product`](api/transforms.md)。
Worked example: `samples/others/scheduling_plant.py`(`linearize_ns=True`)、
`experiments/run_improve_linearize.py` → [`improve_linearize.html`](gallery/improve_linearize.html)。

---

## 4. PWL近似(SOS2) {: #4-pwl-sos2}

### こんな課題ありませんか

- 1変数の非凸関数(効率曲線・べき乗コストなど)を区分線形近似したいが、Big-M で表すと
  バイナリ変数が増えて重くなる。

### 診断で何がわかるか

`numerical_scale`(Big-M候補が presolve 後も残存)や `weak_relaxation`(非線形1変数項が
ボトルネック)の recipe に、区分線形近似の選択肢として案内される。

### 打ち手の仕組み

区分線形関数 y=f(x) は、隣接する折れ点 (bp_k, v_k) の凸結合で表せる。通常この「隣接性」
(non-zero な重みλが連続する2点に限られる)を保証するのに Big-M + バイナリを使うが、
**SOS2制約**(Special Ordered Set type 2: 非ゼロが高々2つ、かつ隣接)を SCIP に直接渡せば、
バイナリ変数もBig-Mも一切使わずに同じ性質を表現できる。SCIP が SOS2 制約専用の分枝規則を
持っているため、余計な補助変数を経由しない分だけ探索が軽い。

### 効果(このリポジトリでの実測)

非凸1変数関数の PWL 近似で、Big-M版は**バイナリ変数20個**を要したのに対し、
SOS2版は**バイナリ0個**で同じ最適値に到達した(FINDINGS §3、
[`sos.html`](gallery/sos.html))。

### 効かないとき・注意

- 1変数関数専用。多変数の非凸項(積など)には使えない → その場合は
  [3. 整数×連続の厳密線形化](#3-integer-x-continuous-linearization) や
  凸包再定式化を検討する。
- 区分数を増やすほど近似精度は上がるが λ 変数も増える(トレードオフ)。

### 使い方

```python
import minlpkit as mk

# f(x)=x^2 を3点で区分線形近似
y = mk.pwl_sos2(m, x, breakpoints=[0.0, 1.0, 2.0], values=[0.0, 1.0, 4.0], name="sq")
```

API: [`mk.pwl_sos2`](api/transforms.md)。
Worked example: `samples/physics_and_control_minlp/pwl_sos.py`、
`experiments/run_sos.py` → [`sos.html`](gallery/sos.html)。

---

## 5. Big-M排除(tight M・Indicator) {: #5-bigm}

### こんな課題ありませんか

- 固定費(施設開設・段取り替えなど)を Big-M でモデル化していて、「M をいくつにすべきか」
  自信がない。
- 診断が `numerical_scale` を出し、`residual_bigm_count` に残存 Big-M があると言っている。

### 診断で何がわかるか

`numerical_scale`(warning)は presolve **後**の残存係数比(`residual_coef_ratio ≥ 1e6`)
または残存 Big-M 件数(`residual_bigm_count ≥ 1`)で発火する。presolve前の生の係数比では
判断しない設計になっている点に注意(次の「効かないとき」参照)。

### 打ち手の仕組み

Big-M 制約 `x ≤ M·u`(u はバイナリ)は M が緩い(実際に必要な値より大きい)ほど LP 緩和が
緩む。打ち手は2つ:

1. **tight M**: 変数境界などから導出できる最小の M に絞る。
2. **Indicator制約**: `u=1 → x ≤ c` のような論理制約を SCIP の Indicator 機能に直接渡す。
   Big-M の値そのものを選ぶ必要がなくなる。

### 効果(このリポジトリでの実測)

緩い Big-M を持つ固定費モデル(8施設)で、純粋LP緩和境界が **1594→7127(+347%)**、
最適値7180にほぼ到達(FINDINGS §3、[`improve_bigm.html`](gallery/improve_bigm.html))。
条件数も緩いBig-Mで κ(A)=3.5e4 → tight化で κ=32 と**100倍以上改善**(FINDINGS §3b)。

### 効かないとき・注意

- **正直な注意点**: 上記の LP 緩和境界の改善とは裏腹に、**既定 SCIP は presolve が緩い
  Big-M を自動でタイト化する**ため、小規模なモデルでは最終的な求解時間は変わらないことが
  多い(素B&Bのノード数 11→9→8 と小さな改善に留まる)。効果が緩和境界の数字ほど
  実感できるのは presolve が効きにくい大規模/複雑な構造のとき。
- `numerical_scale` の閾値は presolve **後**の残存値(真の悪条件 1e6)で判断している。
  presolve前の係数比(例: 1e5)だけを見て「悪い」と判断しないこと — 実測では presolve前
  1e5・presolve後 1.0(Big-M候補 8→0)というケースが典型で、これは発火させない設計
  (FINDINGS §1)。

### 使い方

```python
# Indicator制約(u=1 のとき x <= c)
m.addConsIndicator(x <= c, binvar=u)
```

`mk.linearize_product`/`mk.pwl_sos2` のように専用ヘルパーは無く、PySCIPOpt の
`addConsIndicator` を直接使う。条件数の確認は `matrix_condition(model)`(SVD、solve前)
と `scip_basis_condition(model)`(SCIP LP基底、solve後)。
Worked example: `samples/others/fixed_charge.py`、
`experiments/run_improve_bigm.py` → [`improve_bigm.html`](gallery/improve_bigm.html)、
`experiments/run_condition.py` → [`condition.html`](gallery/condition.html)。

---

## 6. SCIPパラメータチューニング(Optuna)とスイープ {: #6-tuning}

### こんな課題ありませんか

- SCIPのパラメータ(分離/ヒューリスティクス/presolve/分枝規則)が多すぎて、何を触れば
  いいかわからない。
- 「このモデル群(同じ問題クラスの複数インスタンス)に効く設定」を体系的に探したい。

### 診断で何がわかるか

診断は無関係(パラメータチューニングは症状ベースの推薦対象ではなく、モデル構造に依存しない
メタ最適化)。ただし `dual_stall` の recipe は「効果は `mk.compare_variants` で検証」と
案内しており、チューニング後の設定もこの検証ループに乗せる。

### 打ち手の仕組み

SCIP の挙動(分離の強さ・ヒューリスティクスの頻度・presolveの積極性・分枝規則)は
`SCIP_PARAMSETTING`(default/aggressive/fast/off)などで一括制御できる。どの組み合わせが
「固定時間での双対境界」を最大化するかは問題クラス依存で理論的に決め打てないため、
Optuna(TPEサンプラー)でベイズ最適化的に探索する。`mk.sweep` はその一段シンプルな版で、
候補パラメータセットを総当たりして比較する。

### 効果(このリポジトリでの実測)

線形化版plant で固定7秒の双対境界を最大化する設定を探索した結果、
デフォルト **134.8 → 最良 143.7(+6.6%)**。最良設定は
`separating=fast, heuristics=fast, branching=mostinf`(カット/ヒューリスティクスを軽くし
分岐で双対を押す構成)(FINDINGS §3、[`tune.html`](gallery/tune.html))。

### 効かないとき・注意

- 効果は数%オーダーの上積みであり、[3. 厳密線形化](#3-integer-x-continuous-linearization)
  のような定式化の作り込み(+140%)と比べると小さい。**まず定式化を直し、パラメータは
  最後の仕上げ**という順序が妥当。
- 探索は特定のインスタンス(または代表インスタンス群)に対する特化なので、別の規模・構造の
  インスタンスに一般化するとは限らない。運用は代表インスタンス群でチューニングし本番設定を
  固定するのが実務的。

### 使い方

```python
from minlpkit.tune import tune   # extras: uv add "minlpkit[tune]"

result = tune(n_trials=18, time_limit=8.0)
print(result["default_dual"], result["best_dual"], result["best_params"])
```

スイープ(総当たり比較、記録は通常runとしてライブUIでそのまま比較できる):

```python
import minlpkit as mk

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(build_model, param_sets, name="sched", time_limit=10)  # 要 extras viz
```

API: `minlpkit.tune.tune`([APIリファレンス](api/tune.md))、[`mk.sweep`/`mk.rerun`](api/live.md)。
Worked example: `experiments/run_tune.py` → [`tune.html`](gallery/tune.html)、
`experiments/run_sweep.py` → `results/sweep.html`。

---

## 7. ベンダーズ分解 {: #7-benders}

### こんな課題ありませんか

- モデルが「設計/配置を決める部分」と「その決定を所与にした運用/割当を決める部分」に
  自然に分かれる(施設開設→輸送、投資→運用、など)。
- 診断が `decomposable`(good)を出している = 制約-変数のグラフがブロック対角に近く、
  結合制約(異なるブロックをまたぐ制約)が少数しかない。

### 診断で何がわかるか

`decomposable` は「最大結合制約が4グループ以上のブロックにまたがり(`max_linking_groups ≥ 4`)、
かつ重い結合制約(多数のブロックにまたがるもの)が3本以下(`n_heavy_linking ≤ 3`)」で発火。
evidence に「最大結合制約が何グループにまたがるか」「重結合制約は何本か」が出る。

### 打ち手の仕組み

主問題(連結変数 y = 「開設するか」等の少数の意思決定)とサブ問題(y を固定したときの
残り、通常はLP)に分けて交互に解く。サブ問題の双対から**最適性カット**
`η ≥ Q(ŷ) + Σ grad·(y − ŷ)`(サブ費用 Q の y に関する線形下界)を作って主問題に足していく。
主問題の目的(下界)とサブ問題の真の費用(上界)が収束するまで繰り返す。直感的には
「サブ問題を毎回律儀に主問題へ埋め込む代わりに、サブ問題の"感度"だけを主問題に教える」
アプローチ。

### 効果(このリポジトリでの実測)

`facility`(施設配置)を主問題(開設 y)/サブ問題(輸送LP)に分解。単一問題を直接解いた
最適値 1340 に**完全一致**(下界=上界=1340)、**3反復・2カットで収束**
(下界 360→1280→1340、FINDINGS §3、[`benders.html`](gallery/benders.html))。

### 効かないとき・注意

- 構造(結合制約が少数、主問題とサブ問題が分離できる)が前提。診断センサスでは
  `decomposable` は9本で発火しており、ブロック構造自体は珍しくないが、分解が実際に
  計算コストを下げるかは規模次第(小規模なら単一問題を直接解く方が速いこともある)。
- ここに実装した `mk.benders` は**実行可能性カットを扱わない**(サブ問題が常に実行可能に
  なるようモデル化する前提)。実行不能なサブ問題が起こりうる構造には拡張が必要。

### 使い方

```python
import minlpkit as mk

result = mk.benders(master_build, subproblem_solve, max_iter=50, tol=1e-6)
print(result["lb"], result["ub"], result["n_cuts"])
```

`master_build(cuts) -> Model` と `subproblem_solve(y_hat) -> (Q, grad)` の2コールバックだけ
問題固有(詳細は docstring)。
API: [`mk.benders`](api/frameworks.md)。
Worked example: `experiments/run_benders.py` → [`benders.html`](gallery/benders.html)。

---

## 8. 列生成(基礎・双対安定化・price-and-branch) {: #8-column-generation}

### こんな課題ありませんか

- 「取りうるパターン」(裁断パターン、シフトパターン、経路など)が指数的に多く、
  コンパクトな定式化を**そもそも書き下せない**。
- 列生成という言葉は聞いたことがあるが、実際どう実装すればいいかわからない。

### 診断で何がわかるか

専用の diagnose finding はない(`decomposable` の recipe に選択肢として
`mk.column_generation`/`mk.price_and_branch` が案内される場合はある)。列生成が要る場面は
「モデルがそもそも列挙不能」という規模の問題であり、`analyze` にかける前の設計判断に近い。

### 打ち手の仕組み

制限主問題(現在持っている列だけを使った LP: `min Σλ_p s.t. Σ_p col_p·λ_p ≥ rhs, λ≥0`)を
解いて双対 π を得て、その π のもとで「被約コストが負(価値がある)」列を1本だけ
**pricing問題**(通常はナップサック等の小さな最適化)から生成し、主問題に追加する
――を反復する。**列を全部並べずに、必要な列だけをその都度作る**のが要点(直感的には
「無限にある選択肢を、いま損している方向にだけ一本ずつ問い合わせる」)。

- **双対安定化(Wentges)**: 退化問題では双対 π が反復ごとに大きく振動し(tailing-off)、
  収束が遅くなる。安定化中心(最良Farley下界の双対)へ `π̃ = α·π_center + (1−α)·π` で
  平滑化してから pricing に渡すと振動が抑えられる。
- **price-and-branch**: 列生成後、生成済みの列だけを使って整数制限主問題を解く。
  **これは上界のみ**(真の整数最適 ≥ この解とは限らない — 正確には整数解 ≥ 真の最適の保証)。
  厳密な整数最適を保証する branch-and-price には分枝ノードごとの pricing が要るが、
  `lp_lb == int_obj` が成り立てば最適性が(結果的に)証明できる。

### 効果(このリポジトリでの実測)

`cutting_stock`: 総パターン131個のうち**13個(9.9%)だけ生成**して最適LP境界23.55に到達、
8反復で収束(FINDINGS §3、[`colgen.html`](gallery/colgen.html))。**正直な知見**: この
LP境界はコンパクト定式化の材料下界(23.52)と**同等**であり、列生成の価値は「LP強度」では
なく「指数的な列を列挙せず暗黙に扱う」こと(実務ではコンパクトが構築不能な規模で効く)。

双対安定化: 退化 cutting stock(17品目)で反復 **31→25(−19%)**、LP境界382.75は不変
(FINDINGS §3、[`stabilize.html`](gallery/stabilize.html))。α過大(0.9)は過剰安定化で
未収束になる。

price-and-branch: cutting stock で**整数最適24ロール**(LP下界のceil=24と一致 = 最適性
証明済み)([`bnp.html`](gallery/bnp.html))。

### 効かないとき・注意

- **price_and_branch は最適保証がない**。小規模テスト(W=10, 幅[3,4,5], 需要[3,3,3])で
  `price_and_branch=5` に対し全パターン列挙ILPの真の最適=4 という例がある(FINDINGS §4)。
  `lp_lb == int_obj` を確認しない限り「最適」と言い切らないこと。
- PySCIPOptの `getDualsolLinear` は presolve で制約がNULL化され失敗することがある。
  連続LPの双対取得には scipy `linprog` の `res.ineqlin.marginals` を使う方が確実
  (FINDINGS §4、内部実装済み)。

### 使い方

```python
import minlpkit as mk

widths, rhs, W = [3, 4, 5], [3.0, 3.0, 3.0], 10
init = [[3, 0, 0], [0, 2, 0], [0, 0, 2]]

def pricing(duals):
    from pyscipopt import Model
    kp = Model(); kp.hideOutput()
    a = [kp.addVar(vtype="I", lb=0, name=f"a{i}") for i in range(3)]
    kp.addCons(sum(widths[i] * a[i] for i in range(3)) <= W)
    kp.setObjective(sum(duals[i] * a[i] for i in range(3)), "maximize")
    kp.optimize()
    return [round(kp.getVal(v)) for v in a], kp.getObjVal()

res = mk.column_generation(rhs, init, pricing, alpha=0.0)   # alpha>0 でWentges安定化
bnp = mk.price_and_branch(rhs, init, pricing)                # 整数解(上界)+最適性判定
```

API: [`mk.column_generation`/`mk.price_and_branch`](api/frameworks.md)。
Worked example: `experiments/run_colgen.py` / `run_stabilize.py` / `run_bnp.py` →
[`colgen.html`](gallery/colgen.html) / [`stabilize.html`](gallery/stabilize.html) /
[`bnp.html`](gallery/bnp.html)。

---

## 9. GPU warm start(cuOpt) {: #9-gpu}

### こんな課題ありませんか

- 数万〜数十万バイナリ変数の大規模MILPで、時間制限内に**可行解すらろくに見つからない**。
- 「CPUの分枝限定は最適性証明に強いが、初期解探索が遅い」と感じている。

### 診断で何がわかるか

`gpu_primal`(warning)は「線形(非線形なし)・バイナリ1万個以上・等式同士の変数共有が
少ない(`eq_overlap ≤ 1.5`)・可行解が少ないかTTFFが遅い・gapが残る」ときに発火する。
**GPU/cuOptの導入有無に関係なく発火する**設計(問題構造だけで判定。「導入価値の提示」
自体が診断の価値、という考え方)。

### 打ち手の仕組み

cuOpt は「GPU上の primal heuristic エンジン + CPU側 B&B」で、B&B・LP自体はCPUで行うが、
Feasibility Jump / Feasibility Pump 系のローカルサーチをGPUで大量並列評価する。
`mk.cuopt_warmstart` はこれを短時間走らせて見つけた解を SCIP に `addSol` で注入してから
通常の `optimize()` に渡す「GPUが可行解探索、CPU(SCIP)が最適性証明」という分業。
`mk.cuopt_concurrent` は cuOpt をバックグラウンドで並走させ、終了し次第イベントハンドラ
経由で mid-solve 注入する(GPU待ちの直列時間をゼロにする)。

### 効果(このリポジトリでの実測)

GAP large(75,000バイナリ、タイト容量、60秒): 純SCIP gap **22.9%**(解3個)に対し、
cuOpt単体 gap **0.64%**、hybrid(cuOpt注入→SCIP)gap **4.72%**(FINDINGS §7。
成果物は `results/gpu/gap_large_compare.html`、リポジトリ内実行時のみ生成される
ローカル成果物のためドキュメントサイトには未同梱)。xlスケール(240,000バイナリ、120秒)
でも優位は持続: SCIP 20.72% / cuOpt 4.72% / hybrid 7.99%。

### 効かないとき・注意

- **等式制約が変数を共有する構造(集合分割型)には効かない**。集合分割 large(40,000列)では
  cuOptが**可行解ゼロ**(60秒/180秒とも)。ルートLPが退化して停滞し、GPUヒューリスティクスに
  到達しない。判別子は等式の比率ではなく**等式同士の変数共有度**(`eq_overlap`。GAP=1.0で
  有効、集合分割≈10で不発、閾値1.5)。この構造には[8. 列生成](#8-column-generation)を
  検討する。
- 小規模(2,000変数)では純SCIPが上(60秒: SCIP gap 0.43% vs cuOpt 1.37%)。GPUは
  「初期可行解が見つかりにくい大規模MILP」に効く技術であって、小規模には出番がない。
- `cuopt_concurrent` はSCIPのルートLPが時間予算を食い尽くす規模(xlクラス)ではイベントが
  発火せず注入機会がゼロになる。その場合は直列の `cuopt_warmstart` を使う
  (使い分けの実測はFINDINGS §7)。
- GPU機能は完全に任意で minlpkit 本体の依存には何も追加しない。未導入環境では
  `mk.cuopt_available()` が False を返し、呼び出すと導入手順つきの `RuntimeError`。

### 使い方

```python
import minlpkit as mk

m = build_model()                          # 最適化前
res = mk.cuopt_warmstart(m, time_limit=15)  # 要 WSL2+cuOpt、または server_url=... でリモート
m.setParam("limits/time", 60)
m.optimize()                                # 注入解を起点にSCIPが証明を続ける
```

API: [`mk.cuopt_warmstart`/`mk.cuopt_concurrent`](api/live.md)。導入手順・リモートサーバ構成は
[利用マニュアル §7](manual.md#7-gpu-warmstart)。
Worked example: `experiments/run_gpu_heuristic.py` → `results/gpu/*_compare.html`
(ローカル実行成果物)、`experiments/gpu_dashboard.py`(比較ダッシュボード)。

---

## 10. 条件数・数値健全性 {: #10-condition}

### こんな課題ありませんか

- 求解結果が実行環境やSCIPバージョンで微妙に違う、あるいは「怪しい」数値が出る。
- 「係数のオーダーが揃っていない気がする」がどのくらい問題なのか判断がつかない。

### 診断で何がわかるか

`numerical_scale`(warning、[5. Big-M排除](#5-bigm)と共通)は presolve後の残存係数比
(`residual_coef_ratio ≥ 1e6`)を見る。ただしこれは max/min 比であり、**真の条件数の代用には
ならない**(下記参照)。

### 打ち手の仕組み

係数の max/min 比は「レンジの広さ」を見るだけで、行列の悪条件性(数値誤差の増幅度合い)の
正確な指標ではない。真の条件数 κ(A) は係数行列の特異値分解(SVD)の `σ_max/σ_min` で得る
(`matrix_condition`、solve前の定式化診断)。加えて、実際に解いたときの最適LP基底の条件数は
`scip_basis_condition`(SCIPの `getCondition()`)で別途測れる。前者は定式化そのものの
悪条件、後者は「実際に解いたときの基底の不安定度」を測るという意味で相補的。

### 効果(このリポジトリでの実測)

緩いBig-Mで κ(A)=3.5e4、tight化で κ(A)=32(**定式化の選び方が数値健全性を100倍以上左右**)。
`unit_commitment` は LP基底 κ≈2.6e11 と極端で、実際に数値不安定リスクがある領域
(FINDINGS §3b、[`condition.html`](gallery/condition.html))。

### 効かないとき・注意

- 係数の max/min 比だけで「数値問題あり」と早合点しないこと。自然なコスト差(~1e3程度)は
  数値問題ではなく、真の悪条件は presolve後で1e6以上のレンジと見るべき(FINDINGS §1)。
- 条件数を改善する具体的な打ち手は多くの場合「Big-M排除」(節5)や「変数境界のタイト化」
  であり、条件数診断そのものは**症状を数値化する道具**であって、それ単体で解決策には
  ならない。

### 使い方

```python
from minlpkit.collectors.static_diag import matrix_condition, scip_basis_condition

kappa_static = matrix_condition(build_model())      # solve前、SVDベース
m = build_model(); m.optimize()
kappa_basis = scip_basis_condition(m)                # solve後、SCIP LP基底
```

Worked example: `experiments/run_condition.py` → [`condition.html`](gallery/condition.html)。

---

## 11. ライブ監視・run記録・再現(rerun) {: #11-live}

### こんな課題ありませんか

- 長時間の求解を「止まっているのか進んでいるのか」わからないまま待っている。
- 過去に試した設定を後から思い出せない(「あのときの実行はどのパラメータだった?」)。
- パラメータを何通りか試したいが、比較する仕組みがない。

### 診断で何がわかるか

ライブ監視自体は診断ルールとは独立(別レイヤー)。ただし単一run表示にはライブ簡易版の
症状バナー(`detectLiveStall`/`detectNoIncumbent`/`detectHighGapDone`)があり、これは
`collectors/attribution.detect_stalls` と同じ思想の JS 実装。「ライブ簡易判定。全診断は
`mk.analyze` で実施」と明記されており、`mk.analyze` の部分集合であることを隠していない。

### 打ち手の仕組み

TensorBoard型の「書き手/読み手分離」。書き手(`solve_with_monitor`)がソルバーのイベントを
`results/runs/<run_id>/` にファイルとして追記し、読み手(Flask+SSEサーバ)がそれを tail して
ブラウザへライブpushする。求解直前に SCIP パラメータ差分・モデルのfingerprint(変数/制約
内訳)・環境情報・git SHA を自動キャプチャして `meta.json` に残す(`capture=True` が既定)。
これにより「どの条件で解いた run か」が後から辿れる。

`mk.sweep` はパラメータ候補群を総当たりし、**各セットを普通の run として記録する**設計
なので、専用UIを作らずライブUIのrun比較(チェックボックス選択)がそのままスイープ結果比較
になる。`mk.rerun` は記録済み run の `scip_params_diff` を読み出して同じ条件で再求解する
(再現実行)。

### 効果(このリポジトリでの実測)

20秒求解で338 SSEフレームのライブ配信+done確定を確認。実データ検証では
`experiments/run_monitor.py --model plant --time 45` の実行(826イベント、gap 105.8%)に
対してライブ簡易stall判定が正しく発火(windowRate 0.514 < 0.5×overallRate 1.712)、
`detectHighGapDone` も gap 105.8%≥50%で発火することを確認済み(task.md Phase 10-B)。

### 効かないとき・注意

- ライブの停滞バナーは「簡易判定」であり、全項目診断(`weak_relaxation` 等)は出ない。
  本格的な診断は `mk.analyze` を別途実行すること。
- `mk.rerun` は capture の無い run(`capture=False` で求解した旧run)には使えない
  (`ValueError`)。再現性を残したい run は capture をオプトアウトしないこと。

### 使い方

```powershell
# 読み手(開きっぱなし)
uv run python -m minlpkit.live.server   # http://127.0.0.1:5000

# 書き手(別ターミナル)
uv run python experiments/run_monitor.py --model plant --time 120 --gap 0.01
```

```python
import minlpkit as mk

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(build_model, param_sets, name="sched", time_limit=10)
new_run_id = mk.rerun(build_model, df["run_id"][0], time_limit=20)
```

API: [`mk.sweep`/`mk.rerun`/`solve_with_monitor`/`RunLogger`](api/live.md)。
詳細は [利用マニュアル §4](manual.md#4-live)。

---

## 12. 参考: Perspective再定式化(常用非推奨) {: #12-perspective}

### こんな課題ありませんか

- on/off バイナリ×半連続な二次費用(`fc ≥ a·u + b·p + c·p²`、u=0なら p=0)を持つモデルの
  緩和を締めたい、と文献で見た「perspective化」を検討している。

### 診断で何がわかるか

専用の finding はない。`dual_stall` の一般的な推薦の中に理論上の選択肢として位置づけられる
が、下記の理由で minlpkit は積極的には推薦しない。

### 打ち手の仕組み

二次項だけを perspective 化した `fc ≥ a·u + b·p + c·p²/u` は理論上凸包を締める再定式化で、
`c·p² ≤ (fc − a·u − b·p)·u` という一般非線形制約に書き直せる。

### 効果(このリポジトリでの実測、負の結果)

Unit Commitment(on/off × 二次費用)に適用したところ、**既定SCIPではルート双対境界
117067.24→117067.71(+0.0004%、実質不変)**。presolve/分離がbaselineの凸二次を自動で
締めてしまうため。素の分枝限定(presolve/分離/対称性OFF)で比較すると
**113956→57784(−49%悪化)**(FINDINGS §1・§2、[`perspective.html`](gallery/perspective.html))。

### 効かないとき・注意

- **理由**: SCIP は perspective 制約右辺の双線形項(`fc·u`, `u²`, `p·u`)を McCormick で
  緩く緩和してしまい、perspective本来の凸包(rotated SOC相当)の恩恵を活かせない。
  「双線形の新規追加」という意味で [3節](#3-integer-x-continuous-linearization) の
  `n·s≥demand` の逆効果と同型の失敗パターン。
- 等価変換なので最適値自体は不変(縮小4期での実測で32224.44=32224.44と一致)。
- **結論: SCIPに対しては素の凸二次下界の方が有利**。`mk.perspective_quadratic` は
  横展開可能な部品として提供するが、通常は使わない方がよい。

### 使い方(あえて使う場合)

```python
import minlpkit as mk

mk.perspective_quadratic(m, u, p, fc, a=1.0, b=2.0, c=0.5, name="persp")
```

API: [`mk.perspective_quadratic`](api/transforms.md)(docstring に Warning あり)。
Worked example: `experiments/run_perspective.py` → [`perspective.html`](gallery/perspective.html)。
