# 受け入れ検証結果 (Phase 13)

`experiments/acceptance.py` による自動判定。

- 小scale=`small`(最適到達確認, <= 60s) / 既定scale=`default`(30s analyze)
- 受け入れ基準: **30秒で gap>=10%** または **非自明findings発火**(symmetry_info/decomposable 以外)
- 判定: **2/2 PASS**

| model | small status | small obj | small(s) | default gap | nodes | nsols | findings | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| battery_degradation_dispatch | optimal | -179.2 | 1.3 | 4.3% | 7747 | 4 | `numerical_scale` | ✅ PASS |
| thermal_storage_lossy | optimal | 7.357 | 3.0 | 62.2% | 1 | 1 | `numerical_scale` | ✅ PASS |

判定理由(PASS根拠):
- **battery_degradation_dispatch**: 非自明findings numerical_scale
- **thermal_storage_lossy**: gap 62.2% ≥ 10%; 非自明findings numerical_scale

## T10 固有の追加確認(上級ティア: 実行可能性のみ必須、可視化題材としての評価)

T10 の受け入れ基準は T1-T3 と異なり「小scaleで実行可能解が出ること」のみが必須
(最適証明・gap収束は不要)。以下は `mk.analyze` 実測と `minlpkit.collectors.tree`
による空間分枝の有無の追加確認(honest log)。

### battery_degradation_dispatch(蓄電池サイクル劣化コスト内生化ディスパッチ)
- 事業ストーリー: BESS運用者が価格差アービトラージと将来のサイクル劣化コスト
  (Cレート・DoD・外気温のべき乗積で加速)を同時最適化する充放電計画。
- small(24期)は 1.3s で最適(nsols=7)。default(72期)は 30s で **gap 4.3%**、
  **nodes=7747**(spatial branch-and-bound が長時間走った)、`numerical_scale` 発火。
- `minlpkit.collectors.tree.solve_and_collect` で small を追跡すると、収集
  600分枝ノード中 **spatial 290 / root 1**(整数変数を持たないため全て空間分枝、
  最大深さ34)。分枝は `crate_t`・`dod_t` の定義制約(容量 `cap_t` を分母に持つ
  双曲線)由来の真の双線形非凸に起因し、劣化速度べき乗項(Cレート^1.5×DoD^1.3)
  との複合で緩和が緩い。**空間分枝木の実演材料として非常に良好**(整数分枝が
  存在しない「純粋な連続非凸MINLP」の分枝木という、既存モデル群にない性質を持つ)。

### thermal_storage_lossy(蓄熱槽の非線形自然対流損失+ヒートポンプ共有)
- 事業ストーリー: 蓄熱運用者が複数槽の充放熱を、契約電力上限と共有ヒートポンプ
  容量の制約下で計画する。自然対流損失(温度差^1.25)+ COPの温度リフト依存
  (双線形)の二重の非線形構造を持つ。
- **設計時の落とし穴(honest log)**: 当初 `loss >= UA*(dtemp)^1.25` の非線形損失
  制約のみでCOPを定数(3.5)としたところ、small・default とも **1ノード(root)で
  即座に最適到達**(gap 0%)し、空間分枝が一切発生しなかった。原因は
  `x^1.25`(x>=0)が**単変数の凸関数**であり、epigraph形の不等式制約はSCIPの
  凸NLP求解でそのまま厳密に解けてしまうため——自然対流損失のべき指数を1より
  大きくする(タスク仕様どおり物理的に正しい選択)こと自体が、単独では
  「診断的に易しい」構造を生むという発見。**対策**: ヒートポンプのCOPを槽温
  リフト依存にする(`q_charge == (COP_MAX - K_COP*dtemp) * p_elec` という真の
  双線形、カルノー効率低下の定性的傾向を反映した物理的に正当な精緻化)ことで
  非凸性を再導入した。追加後は small で **2194ノード**(spatial branching、
  3.0s)、default で **gap 62.2%**(30s、root で time_limit 到達=ルートLP自体が
  カット分離を繰り返し21秒超かかる重い緩和)。
- **横断的な教訓(T10固有)**: 「物理的に正しい非線形性」が必ずしも「診断的に
  難しい」構造を生むとは限らない——単変数のべき乗則(自然対流損失)は凸なら
  SCIPが凸NLPとして容易に解いてしまう。真の非凸(分枝を要する)を作るには
  **2つ以上の決定変数の積**(双線形/双曲線)が必要であり、T2 `hydro_cascade_
  efficiency`・T3 `microgrid_design_operation`・T10 `battery_degradation_
  dispatch` に続き、本モデルでも「状態変数×運用変数の積」パターン(COP×電力)
  を明示的に追加することで解消した。
- **可視化題材としての評価**: 良好(ただし battery ほど劇的ではない)。default
  はルート1ノードのまま62%のgapを残し、双対境界の停滞(root LPの重い緩和)を
  示す教材として使える。small レベルでは spatial branching(2194ノード)が
  発生し、tree collector の題材としても機能する。

### 総評
2モデルとも実行可能解が確認でき(小scale)、既定scaleでは非自明findings
(`numerical_scale`)発火 + 少なくとも一方(thermal_storage_lossy)は有意なgap
(62.2%)を残した。battery_degradation_dispatch は「整数変数なしの純粋連続
非凸MINLP」という T1-T9 にない分枝パターンを提供し、thermal_storage_lossy は
「凸な単変数非線形項だけでは診断的難度が生まれない」という設計上の教訓を
明示的に実演する対比材料として機能する。
