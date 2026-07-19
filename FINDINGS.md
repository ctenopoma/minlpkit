# MINLP可視化・診断・改善 — 調査結果(開発中に判明した事実)

Phase 1-4 の実装過程で実測・検証した非自明な事実の記録。多くは「現代のSCIPは賢く、
教科書的改善の多くを自動解消する」という現実に関わる。閾値・数値は本リポジトリの
サンプル(scheduling_plant / unit_commitment / facility / fixed_charge / parallel_machines /
graph_coloring)での実測値(2026-07、SCIP via PySCIPOpt 6.2.1)。

## 1. SCIPが自動解消するもの(診断で推薦すべきでない)

| 対象 | 実測 | 含意 |
| --- | --- | --- |
| 緩いBig-M | 係数比 presolve前 1e5 → 後 1.0、Big-M候補 8→0(fixed_charge loose) | presolveが自動でタイト化。手動Big-M対応は典型例では不要 |
| 対称性 | makespan(並列機械)・graph coloring は SCIP対称性ON/OFF × 手動除去ON/OFF の**全4通りが1ノード**で解ける | `misc/usesymmetry`(既定ON)が自動対応。手動の辞書式除去は無効〜悪化 |
| 変数境界 | plant で手動FBBT: ルート双対境界 52.13→52.25(微増) | SCIPのFBBTが基本的タイト化を自動実施 |
| 被約コスト固定 | knapsack を既定SCIPは0ノードで解く。素B&Bだと redcost ON 107 / OFF 204 ノード | SCIPの `propagating/redcost`(既定ON)が自動実施。手動再実装は冗長だが技術自体は有効(素B&Bで−48%) |
| Perspective再定式化(半連続二次費用) | UC: 既定ルート双対境界 117067.24→117067.71(**+0.0004%、実質不変**)、60s gap 0.64%→0.69% | 既定SCIPのpresolve/分離がbaselineの凸二次を自動でここまで締める。遠近化の明示は不要(むしろ下記2で悪化)。等価変換で最適値不変(縮小4期 32224.44一致) |

→ 診断は presolve **後**の残存(`residual_scale`)で判断する。比の閾値は真の悪条件 1e6
(自然なコスト差 ~1e3 は数値問題ではない)。対称性は推薦(warning)でなく情報(good)で示す。

## 2. かえって悪化する「改善」

| 施策 | 実測 | 理由 |
| --- | --- | --- |
| 有効不等式 n·s≥demand を plant に追加 | ルート双対境界 52.13→50.48、時間制限gapも悪化 | n·s 自体が双線形。線形緩和の締めではなく**新たな非凸制約の追加**になる |
| 明示的な辞書式対称性除去(makespan) | ノード 1→24(悪化, SCIP対称性off時) | LP実行可能域を非対称に切り、LPを重くする。SCIPの対称性処理の方が上 |
| Perspective化 `c·p² ≤ (fc−a·u−b·p)·u`(UC, 素の分枝限定) | ルート双対境界 113956→57784(**−49%悪化**) | SCIPは右辺の双線形 fc·u, u², p·u を McCormick で緩く緩和し、遠近関数(rotated SOC相当)の凸包を利用しない。`n·s≥demand` と同型=双線形の新規追加が緩和を締めずに緩む。効かせるにはSOC/Indicatorとして明示的に凸ソルバへ渡す枠組みが要る |

## 3. 真に効く改善(SCIPが自動ではやらない)

| 施策 | 実測 | 効く理由 |
| --- | --- | --- |
| **n·s の整数×連続 厳密線形化(分解)**(plant, energy三重積対応) | **ルート双対境界 52→125(+140%)、25s求解gap 127%→49%、ノード 7578→3840**、最適値不変 | SCIPは双線形にMcCormick緩和を使う。整数nを指示変数δ_vで分解すると ns=Σv·s_v が**厳密**(緩和ギャップ0)。三重積が双線形に落ちる |
| tight Big-M / Indicator(fixed_charge, 8施設) | 純粋LP緩和境界 1594→7127(+347%、最適7180にほぼ到達)、素B&Bノード 11→9→8 | 緩和が締まる。ただし**既定SCIPはpresolveが緩Mを補償**するため小規模では最終解時間は不変 |
| 列生成(Gilmore-Gomory, cutting stock) | 総パターン131個のうち**13個(9.9%)だけ生成して最適LP境界に到達**。LP境界23.55はコンパクト定式化(材料下界23.52)と**同等** | 列生成の価値はLP境界の強さ**ではなく**「指数的な列を列挙せず暗黙に扱う」こと。カッティングストックのコンパクトLP境界は弱くない(材料下界に一致)というのが正しい事実。実務ではパターンが指数的で**コンパクト定式化は構築すら不能**な規模で効く。SCIPは自動でやらない(主問題/pricingをモデラーが与える) |

| **SCIPパラメータのOptunaチューニング**(線形化plant) | 固定7sの双対境界 134.8→143.7(+6.6%)。最良=separating/heuristics=fast, branching=mostinf | 問題クラスへの設定特化はSCIPが自動でやらないメタ最適化。この問題では「カット/ヒューリスティクスを軽くして分岐で双対を押す」が有利 |

| **ベンダーズ分解**(facility) | 主問題(開設)/サブ問題(輸送LP)分解が単一問題の最適値1340に完全一致、3反復・2カットで収束 | SCIPが自動でやらない分解。主問題が小さく保たれサブは独立求解可。診断のブロック構造/結合制約に対応 |
| **列生成の双対安定化(Wentges)**(退化cutting stock) | 反復 31→25(−19%)、LP境界382.75不変 | 安定化中心=最良Farley下界の双対へ π̃=α·π_center+(1−α)·π。α過大(0.9)は過剰安定化で未収束(中庸のαが要)。Neame型(前回smoothed中心)は弱く効かなかった→Wentges型が有効 |
| **SOS2区分線形近似**(非凸1変数) | Big-M版バイナリ20個 vs SOS2版0個で同じ最適値 | SOS2(隣接2重み非ゼロ)でPWLをBig-Mなしに表現。`addConsSOS2`。Indicatorと並ぶBig-M回避手段 |

→ 教訓: MINLPの真の律速は**非凸緩和の弱さ**(plantは74%gapで停滞)。ここはSCIPが自動解消
しないので、整数構造を突いた厳密線形化のような**定式化の作り込み**が効く。パラメータチューニングは
問題クラスに特化させる形で+数%の上積みになる。

## 3c. 改善の横展開(ライブラリ化)

- これまでの改善はサンプル埋め込みで再利用不可だった。横展開は(a)再利用可能コンポーネント+
  診断に紐付く手順、(b)自動化できる変換の自動適用、の2層で対応する(改善は本質的にモデル構造依存
  なので全自動は原理的に無理。SCIPですら再定式化は自動化しない)。
- **整数×連続の積の厳密線形化**は `minlpkit.transforms.linearize_product(model, y, x, ...)` に汎用化。
  scheduling_plant と scheduling の**両方を同じ1行呼び出しにリファクタ**して実証(plant +156%, scheduling +1%)。
  効果は問題依存(易しい問題では小さい)が、ヘルパー自体は横展開できる。
- **PWL-SOS2** も `minlpkit.transforms.pwl_sos2(model, x, breakpoints, values)` に汎用化。
- アルゴリズム型(ベンダーズ/列生成)は全自動化できないので、コールバック方式の**汎用ドライバ**にする:
  `mk.column_generation(rhs, init_cols, pricing_fn)` / `mk.price_and_branch`(branch-and-price=整数最適)/
  `mk.benders(master_build, subproblem_solve)`。問題固有はコールバックだけ。cutting stockで整数最適24ロール
  (最適性証明済み)、facilityで単一問題最適1340に一致。
- **完全自動改善は原理的に不可**(build済みモデルから「どの積を線形化すべきか」等の構造を自動検出できない)。
  横展開は「(a)診断のrecipeが具体的な直し方=使うmk関数+worked exampleを提示 + (b)`mk.compare_variants`で
  before/after検証」の組で実現する(=手順を示す路線)。全自動の魔法ではなく、再利用可能な部品+手順が正解。
- **ライブ可視化/チューニングは extras 化**(Phase 9.1)。`minlpkit.live`(Flask+SSEサーバ・Plotly)と
  `minlpkit.tune`(Optuna)は任意 `pyscipopt.Model` で動く問題非依存の再利用機能なので配布物に取り込むが、
  重量級の追加依存(flask/plotly/kaleido/optuna)をコア必須にせず `[project.optional-dependencies]` の
  extras とし、遅延importガードで未導入時に導入方法を案内する。コアは pyscipopt/pandas/numpy/scipy の4つのみを維持。

## 3b. 数値健全性(条件数 κ(A))

- 係数の**max/min比は κ(A) の代用にならない**。真の条件数は係数行列のSVD(`numpy.linalg.svd`の
  σ_max/σ_min)、または最適LP基底の `model.getCondition()` で得る。
- 実測: 緩いBig-M で κ(A)=3.5e4、tight化で κ(A)=32(**定式化が数値健全性を100倍以上左右**)。
  unit_commitment は LP基底 κ≈2.6e11 と極端で、実際に数値不安定リスク(SCIP 10 の厳密有理MILPが効く領域)。
- `matrix_condition`(静的・solve前)と `scip_basis_condition`(getCondition・solve後)は相補的:
  前者は定式化の悪条件、後者は実際に解いたときの基底の不安定度を測る。

## 4. 測定方法論(交絡を避ける)

- **時間制限での比較は探索動学に交絡される**(制約追加でノード/秒が変わる)。定式化の質は
  **ルート双対境界**か**純粋LP緩和境界**(presolve/cut off)で測ると交絡がない。
- ある定式化の効果を分離するには、補償する機構(presolve/separating/内蔵対称性)を**明示的にOFF**にして
  素の分枝限定で比べる(`presolving/maxrounds 0`, `separating/maxrounds(root) 0`, `misc/usesymmetry 0`,
  `setHeuristics(SCIP_PARAMSETTING.OFF)`)。
- 現代SCIPは小規模MILPを大抵ルート1ノードで解く。改善の効果を見たいなら「効果が現れる規模/構造の
  題材を作る」(本リポジトリの fixed_charge 8施設・graph_coloring 等)。
- **双線形の生McCormick緩和を露出させるには presolve/separating だけでなく `propagating/maxrounds(root)=0`
  も要る**。単体テストで `p<=x·y`(x+y≤2, y∈{0,1,2})の McCormick 上界(=2)と厳密線形化(=約1.33)を
  比べる際、presolve/分離をOFFにしても**伝播(domain propagation/OBBT)だけで双対境界が真の最適1.0まで
  締まって**しまい差が出なかった。伝播も切って初めて生の緩和の差が現れる。SCIPの伝播は小規模双線形を
  ルートで実質解けるほど強い。
- **price-and-branch は「生成列上の制限主問題を整数で解く」ため上界(≥真の整数最適)であって最適保証は
  ない**。小cutting stock(W=10, 幅[3,4,5], 需要[3,3,3])で price_and_branch=5 に対し全パターン列挙ILPの
  真の最適=4。テストでは「LP境界≤真の最適(妥当な下界)、整数解≥真の最適(妥当な上界)、整数解は整数」の
  サンドイッチで正当性を検証するのが適切(真の整数最適一致を課すには列の十分性=full B&Pが要る)。

## 5. PySCIPOpt API の落とし穴

- `getValsLinear(cons)` の**キーは変数名の文字列**(Variableオブジェクトではない)。
- `Variable` に `getName()` は無い → `.name` を使う。
- 分枝は**変換後変数**(`t_`接頭辞)に対して起きる。型は元変数名の辞書引きでなく
  分枝が返す変数オブジェクトの `.vtype()` で取る。
- `NODEFOCUSED` では `getParentBranchings()` が**空**。分枝情報は `NODEBRANCHED` で取る。
- `getSlack` は非線形制約に**非対応**(Warning)。非線形の違反は `getNlRowSolFeasibility(nlrow, sol)`
  (負=違反量)。NlRowは元の制約名を保持する。
- SCIPの**対称性生成子はPySCIPOptから取得不可**(`symmetry`系メソッドなし)。自作検出で代替するが、
  線形制約のみのシグネチャは非線形モデルで**偽陽性**(plantでジョブ間の非線形定数差を無視)→
  全線形モデルのみ健全(`sound`フラグ)。
- ルートLP緩和解は `FIRSTLPSOLVED` イベント + `limits/nodes=1`、`createSol()` に各変数の
  `getLPSol()` を詰める。
- WindowsのSCIPクロックは**1秒粒度** → モニタは Python の `perf_counter` で記録。
- 瞬時に解けるモデルは分枝が起きず attribution 収集が空 → 空DataFrameを安全化しておく。

## 7. GPU primal heuristics(cuOpt 25.10 × SCIP、RTX 5070 Ti / WSL2)

2026-07-19 実測(`experiments/run_gpu_heuristic.py`、各アーム60s)。

| 問題 | 純SCIP | cuOpt(GPU) | hybrid(cuOpt注入→SCIP) | 含意 |
| --- | --- | --- | --- | --- |
| GAP large(75,000バイナリ、タイト容量) | gap **22.9%**(解3個) | gap **0.64%**(diving/heuristicsが即incumbent連発) | gap 4.72%(注入解受理) | 「初期可行解が見つかりにくい大規模MILP」ではGPUヒューリスティクスが圧勝。ノート[[cuOpt_MILP_beta]]の「効く局面」を実測確認 |
| 集合分割 large(40,000列、全等式) | 解2個(21,584) | **可行解ゼロ**(60s/180sとも) | 注入なし=SCIPと同等 | cuOptはルートLP(双対シンプレックス=CPU側)が退化で停滞しGPUヒューリスティクス未到達。`--mip-heuristics-only`(LP不要のFJ直行)でも可行解なし=**等式制約主体はFJ系が苦手**(文献どおり) |

- **cuOptの正体はノートの記述どおり「GPU primal heuristic engine + CPU B&B」**。B&B・LPは
  CPU(23スレッド使用)で、GPUが効くのはFJ/FP/local search のバッチ評価。よって
  LPが重い/等式退化の問題ではGPUの出番が来ないまま時間切れになる。
- 小規模(GAP small、2,000変数)では純SCIPが上(60s: SCIP gap 0.43% vs cuOpt 1.37%)。
  ノートの「効きにくい局面=小規模問題」も実測どおり。
- 運用面: cuOptはLinux専用だが**WSL2実行が公式サポート**。Windows母艦のPySCIPOptから
  `wsl -d Ubuntu cuopt_cli` を叩き、`/mnt/d/...` 共有パスでMPS/solを受け渡す2プロセス構成が
  そのまま成立。cuOptの `.sol` はSCIP互換形式(`変数名 値`+`#`コメント)なので
  `readSolFile`+`addSol` で無変換注入できる(GAPで受理を確認)。
- **FJ系の不発は「等式の多さ」ではなく「等式同士の変数共有」で決まる**: GAPも制約数比では
  等式95%だがcuOpt有効。差は eq_overlap(変数あたり所属等式数)= GAP 1.0 vs 集合分割 ~10。
  診断ルール `gpu_primal` はこの eq_overlap≤1.5 をゲートに使う(eq_shareゲートは誤判別)。
- **WSLの9pファイルシステム(/mnt/<drive>)はcuOptのI/Oを支配的に遅くする**:
  gap_large(MPS 15MB/.sol 0.8MB)で、9p上のMPS読み +約20s、9p上への.sol書き +約19s
  (計: 予算15sのcuOptが実測37s)。MPS/.solともWSLネイティブ/tmpにステージングすると
  実測17sに改善。`mk.cuopt_warmstart`/`mk.cuopt_concurrent` は自動でステージングする。
- **常駐型(`mk.cuopt_concurrent`)のmid-solve注入は成立する**: SOLVINGステージ中の
  イベントハンドラから `createSol`+`trySol` した解は受理され即incumbentになる(実証済み)。
  ただし注入タイミングはSCIPのイベント発火間隔に律速される:
  NODESOLVEDだけではルートの分離ループ中(数十秒)発火せず、LPSOLVED併用で
  「cuOpt完了~20s→注入34s」まで短縮(残差はルートLP再解1回分の粒度で原理的)。
  wall-clockでは直列hybrid 77s(GPU17s+SCIP60s)に対し並走60sで同一解に到達。
- **常駐型の適用境界: SCIPのルートLPが横断できない規模では注入フックが枯れる**:
  GAP xl(240,000バイナリ、120s)はpresolve約6sの後、残り114sが単一のルートLP求解で、
  その間SCIPはNODESOLVED/LPSOLVEDを一切発火しない(実測 n_events=0)= 注入機会ゼロ
  (cuOptのsetpart LP停滞と同型の「LP律速」がSCIP側で発生)。この規模では
  optimize前に注入する直列 `cuopt_warmstart` を使う(xl実測: hybrid gap **7.99%** vs
  純SCIP 20.72%、cuOpt単体 4.72%)。concurrentが効くのは「ルートLPは速いが
  ヒューリスティクスが弱い」中間規模(large: 注入34s時点)。
- **GPU優位はxlスケールでも持続**: gap 4.72%(cuOpt) / 7.99%(hybrid) / 20.72%(SCIP)。
  largeより差は縮む(SCIPも時間比例で改善)が、可行解の質はGPU側が一貫して上。
- **cuPDLP系(GPU一次法)は退化LPの特効薬、ただしcuOpt 25.10のMIP経路には載らない**:
  集合分割large(40,000列)のLP緩和は DualSimplex(CPU)が120sでも未完なのに対し
  **PDLP(GPU)は0.8sで最適**(`--relaxation --method 1`、`run_gpu_lp.py`)。
  しかしMIP本体は `--method 1` を指定してもルートLPがDual Simplexのままで、
  集合分割型MIPの不発はcuOpt側では解消不能(列生成=`mk.column_generation` の領分)。
  Barrier(GPU)は cuDSS threading layer エラー(rc=254)で25.10では動かず。
- インストール: WSL2側 `uv venv --python 3.12` + `cuopt-cu13==25.10.*`
  (`--extra-index-url=https://pypi.nvidia.com`)。RTX 5070 Ti(Blackwell, sm_120)対応済み。
  Python 3.10(Ubuntu 22.04既定)は対象外なのでuvでのPython導入が必須。

## 6. 可視化・配信

- plotly.js はオフライン配信可: `from plotly.offline import get_plotlyjs`(CDN不要、CSP不問)。
- ライブ配信は書き手(ソルバー)/読み手(Flask+SSE)をrunディレクトリのファイルで分離(TensorBoard型)。
- 3D Surface は角度依存で読みにくい。対称box + `aspectmode="cube"` + `eye≈(1.6,1.6,1.15)` が良い。
- 停滞検出は「横ばい(改善イベント不在)」より「**改善レートが平均の半分未満**」の方が実態に合う
  (plantの双対境界は多数の小改善で連続上昇し、劇的な平坦域が稀)。
