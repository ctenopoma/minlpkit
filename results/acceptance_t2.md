# 受け入れ検証結果 (Phase 13)

`experiments/acceptance.py` による自動判定。

- 小scale=`small`(最適到達確認, <= 120s) / 既定scale=`default`(30s analyze)
- 受け入れ基準: **30秒で gap>=10%** または **非自明findings発火**(symmetry_info/decomposable 以外)
- 判定: **4/4 PASS**

| model | small status | small obj | small(s) | default gap | nodes | nsols | findings | 判定 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| weekly_uc_ramp | optimal | 2.701e+06 | 1.4 | 0.0% | 1 | 3 | `numerical_scale`, `symmetry_info` | ✅ PASS |
| hydro_cascade_efficiency | optimal | 3.63e+04 | 1.4 | 28.4% | 7569 | 2 | `weak_relaxation`, `dual_stall`, `numerical_scale` | ✅ PASS |
| gas_pipeline_weymouth | optimal | 893.9 | 0.1 | 0.8% | 1 | 3 | `numerical_scale` | ✅ PASS |
| district_heating_detailed_physics | optimal | 1.813e+04 | 23.5 | 125.1% | 1 | 1 | `numerical_scale` | ✅ PASS |

判定理由(PASS根拠):
- **weekly_uc_ramp**: 非自明findings numerical_scale
- **hydro_cascade_efficiency**: gap 28.4% ≥ 10%; 非自明findings weak_relaxation,dual_stall,numerical_scale
- **gas_pipeline_weymouth**: 非自明findings numerical_scale
- **district_heating_detailed_physics**: gap 125.1% ≥ 10%; 非自明findings numerical_scale

## 調整の試行錯誤で分かった知見(T2)

- **`mk.analyze` 自体のオーバーヘッドが非線形制約数に対して急増する(T2最大の落とし穴)**:
  `collect_metrics` は `solve_and_attribute`/`collect_root_violations`/`residual_scale`/
  `linking_constraints`/`detect_symmetry` のために `build_fn()` を約7回呼び直す。モデルに
  非線形(二次・双線形)制約が多いと、SCIPの空間分枝限定法まわりの前処理(凸性判定・
  McCormick緩和構築・OBBT)のセットアップ自体が重く、これが7回分乗算される。
  `weekly_uc_ramp` を当初案の週次168時間×24ユニット(nvars≈22,500・nconss≈49,500)で
  作ったところ、SCIPの `limits/time=30` は守られているのに `mk.analyze` 全体は**350秒**
  かかった(解の探索ではなく収集器の再構築コストが支配的)。**ソルバーの time_limit を守る
  こと自体は問題を「難しく」しない** — むしろ問題を大きくしすぎると診断ハーネス自体が
  実用的な時間で回らなくなる。T1(数百〜1000変数規模)にならい、T2でも既定scaleは
  変数・制約数を低〜中千のオーダーに抑える方針へ変更した。
- **weekly_uc_ramp は二次燃料費(凸)を落として純粋MILPにしたことで9倍高速化**:
  `c*p^2` の二次コスト項を外し、線形限界費用のみにしたところ `has_nonlinear=False` となり、
  `mk.analyze` の総時間が350秒→32秒に短縮した(非線形制約ゼロなら空間分枝のセットアップが
  発生しない)。難度の源泉は二次コストではなく PTDF 送電網結合+週次規模のMILP組合せに
  絞ったことで、モデルの事業ストーリー(簡易DC潮流=線形近似)とも整合する。
  なお default 規模ではSCIPが強い presolve/heuristics でLP緩和とほぼ一致する解を即座に
  見つけてしまい(gap≈0%)、`numerical_scale`(送電線容量のbig-M的スケール差)の非自明
  findingでPASSを確保した。予備力制約は当初「需要総量」基準にしていたため、送電混雑用に
  線路容量をタイトにすると計画外停電(shed)でバランスを取る解が予備力制約自体に違反し
  infeasibleになった — **予備力は「計画外停電を除いた実供給量」基準に修正**して解消
  (バックストップ=常時可行性の担保は制約同士の整合性まで見ないと機能しない、というT1の
  教訓の延長)。
- **hydro_cascade_efficiency は水力容量に対する需要の比率が唯一のノブ**: 当初、平均貯水量
  基準の水力容量比0.62倍を需要とすると水力だけで需要を常に上回り火力バックストップが
  一度も使われず(目的値≈0)、LP緩和が最適解と一致してgap 0%だった。**満水位(smax)基準の
  容量に対して0.72倍**まで需要を引き上げることで、時間帯・ダム間の水配分に真のトレードオフ
  (高水頭を待つか今すぐ発電するか、灌漑下限との競合)が生まれ、default(ダム5×期22)で
  gap 28.4% + weak_relaxation/dual_stall/numerical_scale が発火した。small はそのままの
  比率だと120秒でも最適証明できず(スケールが小さくても双線形カスケードは分枝に時間を要する)、
  small専用に需要比を0.40へ緩め、ダム2×期8まで縮小してようやく2秒で最適証明できた
  (T1の教訓「小scaleと既定scaleは別のデータで調整してよい」を明示的に踏襲)。
- **gas_pipeline_weymouth はラインパック(配管内ガス在庫)を追加して初めて時間結合が生まれた**:
  当初案は期ごとに独立した定常状態のWeymouth+コンプレッサ制約のみで、期をまたぐ変数結合が
  皆無だったため、SCIPの presolve が各期を独立成分に分解して瞬時に最適化してしまい
  (gap 0%、有意findingsなし)、受け入れ基準を満たさなかった。配管の入口流量と出口流量を
  分離し、両者の差が「ラインパック在庫(≈平均圧力に比例)」の期間変化に等しいという
  制約を追加することで、実在の輸送実務(日中の需要ピークに合わせてラインパックを
  計画的に増減させる)を反映しつつ期をまたぐ結合を作った。default(ノード6×コンプレッサ2×
  期10)で `numerical_scale` が発火してPASS。
- **district_heating_detailed_physics は既存の物理構造を維持したまま scale 引数化するだけで
  維持できた**: ノード数・期数をパラメータ化し、熱源出口温度のランプ制約(熱慣性)を
  追加して期間の独立分解を防いだ以外は、既存の双線形(流量×温度)・二次(流量²の圧損)構造を
  そのまま流用。default(ノード12×期12、708変数)で gap 125.1%(SCIP `getGap()` は
  `(primal-dual)/|dual|` で定義されるため双対境界が弱いと100%を超えうる。バグではなく
  緩和の弱さそのもの)+ `numerical_scale` でPASS。既存センサスの weak_relaxation 発火実績を
  壊していないことを確認済み。
- **横断的な教訓**: T1では「双線形の実行可能性」がボトルネックだったが、T2では
  「`mk.analyze` 自身の計算コスト」が新たなボトルネックだった。既定scaleを決める際は
  SCIPの解の質(gap/findings)だけでなく、**診断ハーネス自体の実行時間**(変数・制約数、
  特に非線形制約数)も同時に制約条件として扱う必要がある。
