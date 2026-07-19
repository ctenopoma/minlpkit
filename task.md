# MINLP可視化→診断→改善 プラン

Obsidianノート「Mixed Integer Programming.md」の「1. 可視化」「2. 収束性改善」を実践する試行。
ソルバーはPySCIPOpt(SCIP)に統一。Pyomoは使わない。パッケージ管理はuv(`uv add`)。

## 全体の流れ(ゴール)

1. **可視化**: 求解プロセスをモニタリングし、停滞・ボトルネックを見える化する(Phase 1-2)
2. **改善提案の可視化**: 可視化から得た「症状」を診断ルールに照らし、「どの改善が向いているか」を提案として提示する(Phase 3)
3. **改善の実施**: 提案された改善(定式化改善・列生成など)を実装し、before/afterを可視化で検証する(Phase 4)
4. **ヘルパーライブラリ化**: 1〜3を一体化した PySCIPOpt ラッパーライブラリに仕立てる(Phase 5)

※ ML(GNN/学習分岐)・LLMはハードウェア/基盤の導入可否判断が必要なため改善候補から除外。
  GPU(cuOpt等)は実機確認によりPhase 11で解禁済み。
  **モデル(定式化)の改善と数理的手法(列生成・分解・被約コスト固定等)を主軸にする。**

## サンプル問題(Phase 0: 土台)— 完了

可視化の実験台として、少し難しめのMINLPを2種SCIPで実装し動作確認する。

- [x] **プラント系Unit Commitment**(`samples/unit_commitment.py`)— gap 0.94% / 4s で解けることを確認
  - 発電/プラントユニットのON/OFF(バイナリ)+ 出力(連続)
  - 二次燃料費 + バルブポイント効果(|sin|項 → 非凸)、起動費、最小連続運転/停止、ランプ制約
- [x] **バッチスケジューリング**(`samples/scheduling.py`)— gap 0.76% / 1s未満で解けることを確認(簡単すぎたため下の拡張版を追加。可視化のベースライン比較用に残す)
- [x] **バッチ反応器スケジューリング(プラント物理入り)**(`samples/scheduling_plant.py`)
  - 反応速度論(Arrhenius: exp(1/T))、転化率(ネストexp)、需要充足(n·s·Xの三重積)、昇温時間(双線形)、除熱制約(有理式相当)を組み込んだ拡張版
  - 300s時間制限で gap 72.5%、10万ノード、可行解19個 → **gap停滞・bound推移の可視化題材として最適**
  - 制約タイプ別の複雑さ(exp/双線形/三重積)を可視化で比較する題材にも使う
  - ジョブ→マシン割当(バイナリ)、バッチ数(整数)×バッチサイズ(連続)の双線形項
  - 処理時間 = a + b·size^0.6(凹べき乗 → 非凸)、納期・水平時間制約

## Phase 1: 収束モニタリング基盤(難易度: 低)— 完了

- [x] `Eventhdlr` で BESTSOLFOUND / NODESOLVED / LPSOLVED を捕捉しDataFrame化(`viz/monitor.py`)
  - SCIPクロックがWindowsで1秒粒度のためPython側wall clockで記録
- [x] Plotlyダッシュボード: bound推移(暫定解マーカー付)・gap対数・primal gap+Primal Integral(`viz/plots.py`, `run_monitor.py` → `results/`)
- [x] plantモデルで gap停滞(74%で停滞)のトラジェクトリ2,266行を取得、可視化を目視確認済み
- 保留: 解の由来の色分け — `Solution.getOrigin()` はヒューリスティクス名を返さない(常に同値)。
  PySCIPOptにヒューリスティクス名を取るAPIが見当たらないため、解番号の表示に変更。
  由来分析をやるならログパース併用が必要(Phase 2以降の検討事項)

### Phase 1.5: ライブ配信サーバ(主流=TensorBoard型に忠実化)— 完了

書き手(ソルバー)と読み手(UIサーバ)を run ディレクトリのファイルのみで分離。
拡張性重視でこの構成を採用(複数run比較=Phase 4、ライブラリ化=Phase 5に直結)。

- [x] `viz/run_logger.py` `RunLogger` — `results/runs/<run_id>/` に meta/events.jsonl/summary を追記
- [x] `viz/server.py` — Flask + SSE。events.jsonl を tail してブラウザにライブpush。plotly.js オフライン配信
- [x] `viz/live_page.html` — 最新run自動選択・SSE購読・Plotly.reactでライブ更新・run切替ドロップダウン
- [x] E2E検証: 20s求解で338 SSEフレームのライブ配信 + done確定を確認
- [x] ユーザによるブラウザ実表示の再現確認済み(2026-07-18)
- 使い方: 読み手 `uv run python -m viz.server`(開きっぱなし)/ 書き手 `uv run python run_monitor.py ...`

## Phase 2: 診断のための可視化(難易度: 中)— 完了(2.a/2.b/2.c すべて)

Phase 3の改善提案の入力となる「症状」を観測できるようにする。旧Phase 2〜4を診断目線で統合。

### 2.a 凸緩和・空間分枝(本丸)

- [x] 2変数トイ問題 z=x·y でMcCormick包絡の締まりをスライダー付き3Dアニメーション化(`viz/mccormick.py`, `run_mccormick.py` → `results/mccormick.html`)
  - 対称box[-2,2]²で古典的鞍型。区分McCormick凸下界を青、真の曲面を灰で重ね、分割数kのスライダー/▶再生で下界が締まる
  - 併せて「最大ギャップ vs k」を2Dで定量表示。ギャップ=(Δx·Δy)/4≈4.0 が 4.0/k で減衰することを確認
  - 静的HTML(plotly.jsインライン・オフライン可)。3Dカメラ/アスペクトは目視調整済み
- [x] 空間分枝木の可視化(`viz/tree.py`, `run_tree.py` → `results/tree.html`)
  - NODEBRANCHEDで分枝ノード(番号/親/深さ/下界/分枝変数と型)を収集、tidy treeレイアウトで描画
  - **MINLP固有の色分け**: 分枝変数の型で spatial(連続=空間分枝)/integer/binary を区別
  - plantで観測: 上層=0-1/整数分枝(割当・バッチ数)、深部(深さ7-15)に空間分枝が集中
    = SCIPが離散決定を固めてから非線形物理変数(tau・k)を空間分枝し非凸緩和を締める構造が可視化できた
  - 分枝回数内訳バー(0-1:175/整数:149/空間:75)、incumbent発見ノードを星で表示
  - 技術知見: 分枝は**変換後変数**(t_接頭辞)に対して起きる → 型は分枝が返す変数オブジェクトの`.vtype()`で取る
    (元変数名の辞書引きは名前不一致で失敗する)。`NODEFOCUSED`では`getParentBranchings()`が空 → `NODEBRANCHED`を使う
- [x] gap停滞地点と「効いた分枝変数」の紐付け(`viz/attribution.py`, `run_attribution.py` → `results/attribution.html`)
  - NODEBRANCHEDごとに(時刻/ノード/大域双対境界/分枝変数と型)を記録し、双対境界の増分Δdualを直前の分枝に帰属
  - 双対境界推移(緑)+ 改善点を型別に色分け + レートベースの改善鈍化区間を灰帯でシェード
  - 改善量の帰属先バー(型別・変数別上位)。Phase 1×2.bの結合成果
  - **plantでの発見**: 双対境界の総改善54のうち**空間分枝の寄与が54%**(t_k_J5等の反応速度変数が最効)。
    = 非凸緩和の締めが最適性証明の律速 → Phase 3で「空間分枝が刺さる変数の境界タイト化・区分線形近似」が改善候補
  - 技術知見: 停滞は「横ばい」より「改善レートが平均の半分未満」で検出する方が実態に合う(改善は連続的で劇的な平坦域は稀)

### 2.b 制約違反・ボトルネック

- [x] 緩和解での非線形制約の違反量ヒートマップ(`viz/violation.py`, `run_violation.py` → `results/violation.html`)
  - FIRSTLPSOLVEDでルートLP緩和解を捕捉、`getNlRowSolFeasibility`で各非線形制約の違反量を測定
  - 相対違反 = 違反量/(|活動値|+1)。制約タイプ×エンティティのヒートマップ + タイプ別ランキング
  - **plantでの発見**: energy(三重積 n·s·(T-T0))が支配的ボトルネック(相対違反~1.0)、次いでconversion(ネストexp 0.45)。
    arrhenius/jobtime/tmaxはタイト。→ Phase 2.cの空間分枝集中(t_k, t_tau)と整合。Phase 3はenergy/conversionの区分線形近似・凸包再定式化が候補
  - 技術知見: NlRowは制約名を保持。`getSlack`は非線形制約に非対応(Warning)。違反はスケール差が桁違い(energy~1e3)→相対化必須
- [x] 線形制約のIIS + スラック可視化(`samples/facility.py`, `viz/bottleneck.py`, `run_bottleneck.py` → `results/bottleneck.html`)
  - plantは線形制約がpresolveで吸収され検証不能 → **検証可能な純粋線形MILP(容量制約付き施設配置)を新規作成**して完遂
  - スラック分析: LP緩和のスラック=0かつ影の価格(双対値)大 = ボトルネック。open_limit(開設上限)が支配的(影の価格-70)
  - IIS: 実行不能版に削除フィルタ法を自作適用。最小矛盾集合 = 全capacity + 吊上げたdemand_C4 + open_limit の6/10本を正しく抽出
  - 技術知見: `getDualsolLinear`でLP影の価格。IIS削除フィルタは build_fn(active集合)でモデル再構築して各制約の要否を判定

### 2.c 数値安定性・問題構造(静的診断)— 2/4完了

`viz/static_diag.py`, `run_static_diag.py` → `results/static_<model>.html`(uc/plant別に生成)
- [x] 係数・RHS・目的・境界の絶対値レンジ(出所別箱ひげ)、max/min比、Big-M検出
  - UC: 比840・Big-M候補(ramp制約のpmax=400)。plant: 比9.5e4(0.004〜380)。悪条件制約ランキングも
- [x] 制約-変数の二部グラフ/ブロック構造(`getConsVars`で接続行列→RCM並べ替え→帯状ブロック可視化)
  - 結合制約の特定: plantのload_M1/M2が全8ジョブグループにまたがる=分解の境界(ベンダーズ/DW分解の適性)
  - UCはramp制約が隣接2時間期を結合(時間展開の分解境界)
- [x] 区間演算による非線形式の関数値レンジ概算(`viz/interval.py`, `viz/plant_terms.py`, `run_interval.py` → `results/interval.html`)
  - 実Interval演算クラス(+,-,*,/,exp,pow)を実装、plantの実定数・境界で各非線形項の値域を計算
  - **energy(n·s·(T-T0), 値域[100,38400])が最大幅=最も緩和が緩いと静的予測 → Phase 2.bの違反観測と一致**(予測が的中)
  - 知見: arrhenixは値域広いが単変数expのため実際の緩和はタイト。多変数積(energy/demand/cooling)で「広い値域×緩い緩和」が重なるのが真の律速
- [x] 対称性の兆候検出(`viz/symmetry.py`, `run_symmetry.py` → `results/symmetry.html`。`samples/parallel_machines.py`新規)
  - 検証用に恒等並列機械モデルを新規作成。1-hop color refinement(変数の型・目的・境界・所属制約の形状と自身の係数)で入替可能な変数群を検出
  - parallel_machines: 5群・32/33変数が対称(機械対称+等処理時間ジョブ)。facility: 0群(偽陽性なし)。SCIP自身の検出(生成子6個)とも整合

## Phase 3: 改善提案の可視化(診断ルール → 推薦)— 完了

Phase 1-2の観測量から「どの改善が向いているか」を機械的に判定し、ダッシュボードに提案として表示する。

- [x] 診断ルール表をコード化(`viz/diagnose.py`: `Rule`と`RULES`、`evaluate(metrics)`)。6ルール実装
- [x] 診断サマリダッシュボード(`run_diagnose.py` → `results/diagnose_<model>.html`)
  - `collect_metrics`がPhase 1-2の収集器を実際に走らせて観測量を集め、ルール適用→症状カード(症状/原因/推薦/根拠/参照リンク)表示
  - plant: 4症状検出(緩和弱[重大]/値域広/係数桁違い/分解可能[好機])。parallel: 対称性1件。facility: 0件
- [x] `minlp-diagnose` スキル作成(診断ルール表+健全性ルール)
- **重要な健全性修正**: 対称性検出は非線形制約があると偽陽性(plantで誤発火)→ 全線形モデルのみ`sound=True`とし、
  診断ルールは`sym_sound`が真のときだけ発火。SCIPの「plantはno symmetry」と整合。空attribution(瞬時解モデル)も安全化

### 診断ルール表(初版)

| 症状(可視化で観測) | 疑われる原因 | 推薦する改善 |
| --- | --- | --- |
| dual bound停滞(primalは更新されるがgapが縮まらない) | 緩和が弱い(Big-M、非凸項の緩和が緩い) | Big-M排除(Indicator/SOS制約)、変数境界のタイト化、有効不等式の追加 |
| primal解の発見が遅い/少ない | 可行解探索が困難 | カスタムヒューリスティクス、MIP Start(初期解注入) |
| ノード数爆発 + 同コスト解が多数 | 対称性 | 辞書式順序制約による対称性除去 |
| 変数数が巨大でLP解の大半が0 | 列が過剰 | **列生成法**(+ 双対安定化)、被約コスト固定 |
| 制約-変数グラフがブロック対角 + 結合制約少数 | 分解可能構造 | ベンダーズ分解 / Dantzig-Wolfe分解 |
| 係数レンジが桁違い | 数値的不安定 | スケーリング、係数の再定式化 |
| 終盤に目的関数改善が停滞(tailing-off) | 双対変数の振動 | 安定化(Stabilization)、restart制御 |
| 特定の非線形制約に違反が集中 | その制約の緩和が支配的ボトルネック | 区分線形近似、凸包再定式化、変数分割 |
| 探索後半も問題サイズが縮まない | 変数固定が効いていない | 被約コスト固定法、presolve強化・パラメータ調整(Optuna) |

## Phase 4: 改善の実施と効果検証 — 完了(効果検証harnessの汎用化はPhase 5へ)

Phase 3の提案に従い改善を適用。効果が確認できないモデルは確認できる問題を作って検証(方針厳守)。

- [x] **Big-M → Indicator/SOS**(`samples/fixed_charge.py`, `run_improve_bigm.py` → `results/improve_bigm.html`)
  - 診断 numerical_scale の対応。緩いBig-Mを持つ固定費モデル(8施設)を検証用に作成
  - **純粋LP緩和境界: loose 1594 → tight/indicator 7127(+347%、最適値7180にほぼ到達)**、素B&Bノード 11→9→8
  - 正直な知見: **デフォルトSCIPはpresolveが緩いBig-Mを自動で締める**ため小規模では最終解時間は不変。
    効果はLP緩和境界(定式化の質)で明確に出る。大規模/presolveが効きにくい構造で下流に効く
- [x] **対称性除去の検証**(`samples/graph_coloring.py`新規): グラフ彩色(色対称性)で2×2実験。
  **SCIP内蔵対称性ON/OFF × 明示的除去ON/OFF の全4通りが1ノードで解けた** = 現代SCIPは典型インスタンスで
  対称性を自動解消する。手動の辞書式除去は不要という結論(makespanでの負の結果と一致)
- [x] **診断のSCIP-aware化**(ユーザー指摘対応): SCIPが自動処理する分は推薦しない
  - Big-M/数値スケールは`residual_scale`(presolve後)で判断。緩いBig-M(比1e5→presolve後1.0/bigm0)は
    発火させない。残存Big-M(uc ramp pmax=400)・真の悪条件(残存比≥1e6, plant≈4.5e7)のみ発火。比閾値1e3→1e6
  - 対称性は推薦(warning)→情報(good)へ降格し「SCIPが自動処理・通常不要」と明示(`symmetry_info`)
  - `viz/static_diag.py`に`residual_scale`追加、`viz/diagnose.py`・`run_diagnose.py`を更新、`minlp-diagnose`スキルに原則追記
- [~] **変数境界タイト化(plant)**: ルート双対境界 52.13→52.25 と微増(SCIPのFBBTが既に強い)。
  有効不等式 n·s≥demand は双線形なので逆効果(50.48に悪化)。plantでは効果限定的という知見を記録
- [x] **n·s 厳密線形化(整数×連続の分解)**(`scheduling_plant.build_model(linearize_ns=True)`, `run_improve_linearize.py` → `results/improve_linearize.html`)
  - 診断[重大]weak_relaxation(energy三重積)への再定式化。整数nを指示変数δ_vで分解し ns=Σv·s_v を厳密表現(緩和ギャップ0)
  - **ルート双対境界 52→125(+140%)、25s求解gap 127%→49%、ノード 7578→3840、最適値不変** = 実モデルで大幅改善
  - SCIPはMcCormickしか使わないため自動では得られない真の改善。診断→再定式化→検証が実モデルで機能
- [x] **調査結果の資産化**(`FINDINGS.md`): 開発中に判明した非自明な事実(SCIP自動解消・効く/効かない改善・API落とし穴・測定方法論)を整理
- [x] **列生成法(Gilmore-Gomory)**(`samples/cutting_stock.py`, `viz/colgen.py`, `run_colgen.py` → `results/colgen.html`)
  - restricted master(連続LP、双対はscipy linprogで確実に取得)+ pricingナップサック(SCIP)を反復
  - cutting stock: 総パターン131個のうち**13個(9.9%)だけ生成して最適LP境界23.55に到達**、8反復で収束(pricing値→1.0)
  - 正直な知見: LP境界はコンパクト定式化(材料下界23.52)と**同等**。列生成の価値はLP強度でなく「指数的な列を列挙せず暗黙に扱う」こと(実務ではコンパクトが構築不能な規模で効く)。SCIPが自動でやらない再定式化
  - 技術知見: PySCIPOptの`getDualsolLinear`はpresolveで制約NULL化し失敗 → 連続LPの双対はscipy linprog(`res.ineqlin.marginals`)が確実
- [x] **被約コスト固定法**(`samples/knapsack.py`, `run_improve_redcost.py` → `results/improve_redcost.html`)
  - SCIPは redcost 伝播器(既定ON)で自動実施 → 手動再実装は冗長。方針どおり内蔵機能のON/OFF比較で価値を実証
  - knapsack(強相関45品): 既定SCIPは0ノード。素B&BだとON 107 / OFF 204 ノード(−48%)= 技術は有効だがSCIP提供
  - 診断は「手動実装」でなく「SCIP既定で有効」として扱うのが正しい(FINDINGS.md)
- [x] **パラメータチューニング(Optuna)**(`viz/tune.py`, `run_tune.py` → `results/tune.html`)
  - 線形化plantで固定7sの双対境界を最大化するSCIP設定(分離/ヒューリスティクス/presolve/分岐)を探索
  - **デフォルト134.8→最良143.7(+6.6%)**。最良=separating/heuristics=fast, branching=mostinf(カット/ヒューリスティクスを軽くし分岐で双対を押す)
  - SCIPが自動でやらない問題クラス特化のメタ最適化。運用は代表インスタンス群でチューニングし本番設定を固定
- [x] **効果検証の統合**: `minlpkit.compare_variants` で汎用harness化(Phase 5で実装)

## Phase 5: ヘルパーライブラリ化 — 完了

Phase 1-4の成果を PySCIPOpt をラップする一体の `minlpkit` パッケージに再構成。

- [x] API設計・実装(`minlpkit/`): `analyze(build_fn) → Report(metrics+findings)`、`Report.dashboard()`、
  `compare_variants({name: build_fn})`、`RULES`/`evaluate`。`collect_metrics`がPhase 1-4の収集器を統合
- [x] model非依存化: パイプラインは `build_fn`(zero-arg callable→Model)を受け、samples依存を排除
  (区間演算などmodel固有部分は `interval_terms_fn` で任意注入)
- [x] 診断ルールのプラガブル化: `mk.RULES`(list)に `Rule` を追加可能。`evaluate(metrics)` で適用
- [x] 一気通貫デモ(`demo.py`): analyze(plant)→診断→推薦(n·s線形化)適用→compare_variants で before/after。
  実行で ルート双対境界 52→125(+140%)、gap 137%→58% を確認、`results/report_plant.html` 出力
- [x] 技術知見: `build_fn()`の一時Modelはローカルにdelせず保持しないとPySCIPOptがsegfault(反復中GC)
- [x] 自作スキルのAPI追記(minlp-viz/diagnoseにminlpkit参照を追加)

## 技術網羅監査(ノート非ML/GPU/LLM技術 vs 実装状況)— 2026-07-18

ノート「Mixed Integer Programming.md」の ML/GPU/LLM に依存しない技術を全て洗い出し、実装状況を照合。
凡例: ✅完了 / ⚠️簡易・部分実装 / ❌未着手。

### 可視化(1章)
- ✅ gurobi-logtools風モニタ(Eventhdlr→DataFrame→Plotly, bound/gap/stall)
- ✅ IIS + スラック可視化(`bottleneck.py`)※ただし下記⚠️参照
- ✅ **Model Analyzer 条件数 κ(A)**(`viz/static_diag.py`: `matrix_condition`/`scip_basis_condition`, `run_condition.py` → `results/condition.html`)
  - 静的 κ(A)=σ_max/σ_min(係数行列のSVD, solve前)+ SCIP LP基底 κ(getCondition, solve後)の両方を実装
  - 緩いBig-M κ(A)=3.5e4 vs tight=32(定式化の悪条件を検出)、UCのLP基底κ=2.6e11=実際の数値不安定を検出
  - 従来の係数max/min比の代用でなく真の κ(A) で診断可能に

### 分枝限定の改善(2.c)
- ✅ 列生成法(Gilmore-Gomory, `colgen.py`)
- ✅ **列生成の双対安定化(Wentges smoothing)**(`viz/colgen.py` alpha引数, `run_stabilize.py` → `results/stabilize.html`)
  - 安定化中心(最良Farley下界の双対)へ双対を平滑化 π̃=α·π_center+(1−α)·π。誤価格付け時は真の双対にフォールバック
  - 退化cutting stock(17品目)で **31→25反復(−19%)**、LP境界382.75不変(最適性維持)。α過大(0.9)は過剰安定化で未収束
- ⚠️ **被約コスト固定法**: ノートは手動固定 `r_j>(PB−DB)⟹x_j=0` を記載。**SCIP内蔵redcostのON/OFF実証で代替**
  (SCIPが自動実施のため手動は冗長という判断。FINDINGS.md)
- ❌ **Strong branchingの部分適用 / 擬似コストのオンライン更新 / restart制御**: 個別実装なし
  (Optunaで分岐規則を触った程度。SCIP内蔵に依存)
- ⚠️ 対称性検出: 1-hop color refinement(完全な自己同型群でない。全線形に健全性限定)
  — **対応不要で確定(ユーザー判断 2026-07-19)**。精度を上げてもSCIPが自動処理するため診断の結論が変わらない
- ⚠️ IIS: 線形制約のみ(非線形IIS非対応の割り切り)
  — **対応不要で確定(ユーザー判断 2026-07-19)**。非線形は各判定がMINLP実行可能性判定になり既約性の保証が壊れる。
  実行不能な非線形モデルに実際に遭遇したら「近似IIS(既約性非保証と明記)」を検討する余地のみ残す

### 数理構造的アプローチ(2.d)
- ✅ 対称性排除・辞書式順序(実装+検証。SCIPが自動処理と判明)
- ✅ Indicator制約でBig-M回避(`fixed_charge.py`)
- ✅ Optuna自動チューニング(`tune.py`)
- ✅ **ベンダーズ分解**(`viz/benders.py`, `run_benders.py` → `results/benders.html`)
  - facilityを主問題(開設y)/サブ問題(輸送LP)に分解。サブの双対から最適性カット η≥Q(ŷ)+Σg_i(y_i−ŷ_i)
  - **単一問題の最適値1340に完全一致(LB=UB=1340)、3反復・2カットで収束**。下界360→1280→1340が上界に到達
  - サブ問題の双対はscipy linprog。総容量≥総需要の集約カットでサブを常に実行可能化(実行可能性カット不要)
- ✅ **SOS制約(SOS2区分線形近似)**(`samples/pwl_sos.py`, `run_sos.py` → `results/sos.html`)
  - 非凸関数のPWL近似を SOS2(隣接2重み)で表現=Big-M不要。SOS2版バイナリ0個 vs Big-M版20個で同じ最適値
  - `addConsSOS2` を使用。診断の「区分線形近似」推薦の実装選択肢

### 新パラダイム(4章、非ML)
- MDD(多値決定グラフ): **対象外**(ユーザー判断 2026-07-18)
- 量子(QUBO/イジング)は専用ハード前提のため対象外

### 埋めるべき優先順位(価値順)
1. ~~ベンダーズ分解~~ ✅完了(`benders.html`)
2. ~~真の条件数 κ(A) 診断~~ ✅完了(`condition.html`)
3. ~~列生成の双対安定化~~ ✅完了(`stabilize.html`)
4. ~~SOS制約~~ ✅完了(`sos.html`)

**→ 埋めるべき優先順位の全4項目 完了。ML/GPU/LLM非依存のノート技術は、実装可能なものは全てクリア。**
残る簡易/未着手は Strong branching制御群(SCIP内蔵依存で意図的)のみ。MDD・量子は対象外(ユーザー判断)。

## Phase 7: 改善の横展開(ライブラリ化)— 着手

これまでの改善はサンプル埋め込み(再利用不可)だった。横展開には(a)汎用コンポーネント+
診断に紐付く手順、(b)自動化できる所の自動化、の2層で対応する。

### 7.1 モデリング変換ヘルパー(任意モデルに適用可能)
- [x] `minlpkit.transforms.linearize_product(model, y_int, x_cont, ...)`: 整数×連続の積の厳密線形化を汎用化
  - scheduling_plant と scheduling を**同じヘルパー1行呼び出しにリファクタ**(埋め込みロジック排除)
  - 横展開実証: plant ルート双対 52→133(+156%)、scheduling 132→133(+1%、元々易しい)。同じ関数が両モデルで機能
- [x] `minlpkit.transforms.pwl_sos2(model, x, breakpoints, values)`: PWL-SOS2化を汎用ヘルパー化(pwl_sos.pyから抽出)
- [x] `minlpkit.transforms.perspective_quadratic(model, u, p, fc, a, b, c, name)`: 半連続二次費用の遠近化を汎用化
  - 事前検証(8.1)の結論: SCIPには効かない(既定で不変・素だと悪化)が、部品として横展開可能な形で追加・文書化

### 7.2 アルゴリズムフレームワーク(コールバック方式ドライバ)— 完了
- [x] `minlpkit.column_generation(rhs, init_cols, pricing_fn, alpha)`: 列生成を汎用ドライバ化(問題固有はpricing_fnのみ)
  - cutting stockで LP境界23.545(既存一致)を再現。ベンダーズ/facilityも `master_build`/`subproblem_solve` コールバックで LB=UB=1340 一致
- [x] **branch-and-price**(`minlpkit.price_and_branch`, `run_bnp.py` → `results/bnp.html`)
  - 列生成でLP下界→生成列上の整数主問題で **整数最適24ロール**(LP下界ceil=24と一致=最適性証明済み)。これまでLP境界止まりだった列生成を整数解まで
- [x] `minlpkit.benders(master_build, subproblem_solve)`: ベンダーズを汎用ドライバ化。埋め込み(viz/benders.py)をコールバック方式に

### 7.3 診断→改善の手順化(procedure)— 完了
- [x] 診断の各 finding に **recipe(使うminlpkit関数 + worked exampleサンプル)** を紐付け(`viz/diagnose.py` Rule.recipe)
  - `report_plant.html` に「手順」行として表示。例: 緩和弱→`mk.linearize_product`/`mk.pwl_sos2`、分解可能→`mk.benders`/`mk.price_and_branch`
  - これで診断は「症状→原因→推薦→**具体的な直し方(API+例)**→根拠」まで一気通貫の実行可能な手順になった
- [x] 自動改善の方針: 完全自動(build済みモデルから積構造を自動検出して変換)は原理的に不可
  → recipe(手順)+ `mk.compare_variants`(before/after検証)の組で「手順を示す」路線を採用。honestに文書化(FINDINGS 3c)

## Phase 7 完了 — 改善の横展開が確立
- 変換型: `mk.linearize_product` / `mk.pwl_sos2`(任意モデルに1行適用)
- アルゴリズム型: `mk.column_generation` / `mk.price_and_branch`(branch-and-price)/ `mk.benders`(コールバック方式)
- 手順型: 診断のrecipeが各症状に具体的な直し方(API+worked example)を提示

## Phase 8: 残件(Perspective / パッケージ化 / UX)— 着手(サブエージェント委譲)

GPU(実機なし)とForgeは保留。作業はOpus/Sonnetサブエージェントに委譲。

- [x] **8.1 Perspective再定式化の検証→ヘルパー化**(Opus): UCの on/off×二次費用 に perspective
  (c·p² ≤ (fc−a·u−b·p)·u)を適用。ルート境界で事前実測。**負の結果**:
  既定SCIPではルート双対境界 117067.24→117067.71(+0.0004%、実質不変)=presolve/分離が
  baselineを自動補償。素の分枝限定(presolve/sep/heur/sym OFF)ではむしろ 113956→57784(**−49%悪化**)
  =SCIPが右辺の双線形(fc·u,u²,p·u)をMcCormickで緩く緩和し遠近の凸包を利用しないため。
  最適値は縮小4期で 32224.44=32224.44 と一致(等価変換)。方針どおりヘルパー
  `mk.perspective_quadratic` は横展開部品として追加(「SCIPには素の凸二次が有利」の知見付き)。
  → `run_perspective.py` / `results/perspective.html`。7.1の該当行も[x]化。FINDINGS.md 1・2節に追記
- [x] **8.2 minlpkitの真のパッケージ化+テスト**(①③完了後): minlpkitが依存していた
  viz収集器6本(diagnose/attribution/tree/static_diag/symmetry/violation)を `minlpkit/collectors/`
  へ実体移動し、viz側は `from minlpkit.collectors.X import *`(+`__getattr__`)の後方互換シムに
  差し替え(既存 run_*.py・demo.py・viz.server は無修正で動作)。pyproject を hatchling で
  パッケージ化(wheel対象=minlpkitのみ、実行時依存=pyscipopt/pandas/numpy/scipy、viz用の
  flask/optuna/plotly/kaleidoはdev)。pytest 14本(transforms/frameworks/diagnose/pipeline、
  全て実SCIP)全パス。別プロジェクトで `uv add --editable` 導入→`import minlpkit`+`mk.linearize_product`
  動作を実証。demo.py・run_diagnose も回帰OK
- [x] **8.3 UX充実**(Sonnet): `viz/server.py`に`/api/runs/<id>/events`(全イベント一括JSON)と
  `/results/<file>`(パストラバーサル防止付き静的配信)を追加。`live_page.html`に比較モード
  (run A青/run B オレンジで双対・primal・gapを重ね描画、凡例にrun名)、runセレクタの
  「モデル名+開始時刻+status+最終gap」表示、Primal/Dual/最終gapタイルのライブ更新、
  gapチャートの現在値注釈、成果物ギャラリーへのリンクを追加。単一run表示(SSE/自動選択/done)は現状維持

## Phase 9: リポジトリ整理・ドキュメント整備 — 完了

- **整理**: 調査用CLI `run_*.py` 21本を `experiments/` に集約(パス修正込み)。全21本+`demo.py`+pytest14本+`viz.server`(`/`・`/results/index.html` が200)を実行検証、全て正常。stale `__pycache__` 削除。`.claude/skills/`(minlp-run/diagnose/viz)と `CLAUDE.md` のパスを新配置に更新。
- **ドキュメント**: `README.md` / `docs/index.md` / `docs/manual.md` / `docs/api/{pipeline,compare,transforms,frameworks,diagnose}.md` / `mkdocs.yml` を新規作成。公開API(`__all__` 12個)+ `Report` + `collectors.diagnose` の docstring を Google スタイル(Args/Returns/Example)に整備、doctest 50例合格。マニュアル診断ルール表は `collectors/diagnose.py` の6ルール(recipe付き)と一致。
- **MkDocs自動リファレンス**: `mkdocstrings`(google, show_signature_annotations)で docstring から API リファレンスを自動生成。公開APIの引数・返り値に型注釈を補完し、`uv run mkdocs build --strict` を **警告ゼロ(exit 0)** で通過。
- **最終検証**: `pytest -q` 14本パス、`demo.py` 正常(plant ルート双対 52→133)、experiments 5本(diagnose/mccormick/condition/bnp/monitor)が `results/` に出力、README/manual のコード例2本が動作。`site/`・`__pycache__` が配布物でない旨を README に注記。

## Phase 9.1: ライブ可視化 / チューニングの extras 化 — 完了

- **設計**: `minlpkit.live`(モニタ/ログ/Flask+SSEサーバ/Plotlyダッシュボード)と `minlpkit.tune`
  (Optuna)は任意の `pyscipopt.Model` で動く問題非依存の再利用機能。従来 `viz/` 残置=配布物外だったが、
  **extras(オプショナル依存)として配布物に取り込む**。コア依存(pyscipopt/pandas/numpy/scipy)は不変。
- **格上げ**: `viz/{monitor,run_logger,server,plots}.py`+`live_page.html` を `minlpkit/live/` へ、
  `viz/tune.py` を `minlpkit/tune.py` へ実体移動(内部相対import化)。`viz/` 側は collectors と同じ
  再エクスポートシム(`from minlpkit.X import *` + `__getattr__`)に差し替え。`viz/server.py` シムは
  `if __name__ == "__main__": main()` を持ち `python -m viz.server` 起動を維持。
- **extras**: `[project.optional-dependencies]` に `viz = [flask,plotly,kaleido]` / `tune = [optuna]`。
  dev グループは `minlpkit[viz,tune]` を取り込んで一元管理。**遅延importガード**で extras 未導入時は
  `uv add "minlpkit[viz]"` 等を案内する ImportError。配布名を import 名に合わせ `mip`→`minlpkit` にリネーム。
- **wheel**: hatchling が `minlpkit/live/live_page.html` を含むパッケージ内データを既定同梱(build して確認)。
- **docs**: `docs/api/{live,tune}.md` 追加、mkdocs nav 更新。公開関数(solve_with_monitor/RunLogger/build_dashboard/
  tune 等)を Google スタイル docstring 化。`mkdocs build --strict` exit 0。
- **検証**: pytest 14本パス / mkdocs strict exit 0 / run_monitor(シム経由)/ `python -m viz.server` と
  `python -m minlpkit.live.server` の両方で `/`・`/api/runs` が200 / `tune(n_trials=2,time_limit=3)` /
  外部一時プロジェクトでコア導入=依存4つ+`import minlpkit.live` 案内エラー・extras導入=flask/optuna/plotly入り
  import可 / demo.py 回帰(root dual 52→133)。

## Phase 10: 可視化アップデート(実験管理=最適化MLOps)— 完了

方針: Hydra本体は依存に入れない(軽量な自前キャプチャ)。順序 C1→C2(+A)→B→C3。

- [x] **C1: run条件の自動キャプチャ**(Opus): `solve_with_monitor(..., logger=, capture=True)` が
  求解直前(setParam後・optimize前)に `minlpkit.live.capture_run_conditions(model)` を呼び、
  `meta.json` の新キー `capture` に自動保存。中身: **scip_params_diff**(素の`Model().getParams()`との差分。
  clocktype既定=2のため通常は limits/* のみ、heurOFF等で数十個)・**fingerprint**(n_vars/n_bin/n_int/
  n_cont/n_conss/n_linear/n_nonlinear/conss_by_handler/objective_sense/name、presolve前)・**env**
  (minlpkit/python/pyscipopt/scip版・os)・**git_sha**(取れる場合のみ、subprocess)。各項目は独立try/except
  で欠落可(求解は止めない)。後方互換: 既存キー維持・旧runは server が200で読める。RunLogger に
  `update_meta` 追加。テスト tests/test_capture.py(4本)、doctest Example、docs/api/live.md 追記済。
- [x] **C2+A: runs一覧テーブルUI + UI刷新**(Sonnet): `minlpkit/live/live_page.html` をTensorBoard型
  2ペイン(左サイドバー幅320px=runs一覧テーブル / 右メインパネル)に刷新。
  - サイドバー: モデル名/開始時刻/status/gap/nodesの列、列ヘッダクリックでソート(昇降トグル)、
    テキストフィルタ(モデル名/status部分一致)。5秒間隔で`/api/runs`をポーリングし再描画
  - 行クリック=単一run表示(従来のSSEライブ・自動最新run選択・doneイベント確定は無変更で維持)、
    チェックボックス=比較選択(2〜8run、チェック順に固定パレット
    `["#2a78d6","#008300","#e87ba4","#eda100","#1baf7a","#eb6834","#4a3aa7","#e34948"]`を割当。
    9run目以降はチェックボックスをdisabledにして選択不可)
  - 比較時: 選択N runの dual(実線)/primal(点線)を`/api/runs/<id>/events`をN回並列取得して重ね描き、
    gapチャートも同様に重ね描き。凡例は「モデル名(開始時刻)」、タイルにgap/primal/dual/nodesを表示
  - 単一run時: 従来のタイル+bounds/gapチャートに加え、新規「run詳細」折りたたみ(`<details>`)パネルを追加。
    `/api/runs/<id>/events`のmeta.captureから scip_params_diff(表)・fingerprint(変数/制約内訳)・
    env・git_sha を表示。captureが無い旧runは「記録なし」
  - デザイン統一: ヘッダバー(タイトル+ギャラリーへのリンク)を新設、既存CSS変数(--surface等)を維持しつつ
    2ペインのTensorBoard/MLflow系の実務密度感に刷新
  - サーバ側: `minlpkit/live/server.py`の`/api/runs`が`capture`をフルで返さず要約
    `capture_summary`(n_params_diff/fingerprintの変数・制約内訳/git_sha短縮7桁)に差し替え。
    フルcaptureは従来通り`/api/runs/<id>/events`のmetaにある(新規エンドポイントは追加せず)
  - 検証: node --check相当でJS構文OK、サーバ起動して`/`・`/api/runs`が200、sched/plant各1本の
    新規run(capture付き)を追加投入して一覧反映・events取得(200・meta.captureあり)を確認、
    旧run(captureなし、7本)混在でも`/api/runs`が200(capture_summary省略で後方互換)。
    pytest 18本パス、`mkdocs build --strict` exit 0
- [x] **B: ライブ診断**(Sonnet): 単一run表示に症状バナー+ライブ指標タイルを追加。
  - 純関数を `minlpkit/live/live_rules.js` に一箇所だけ実装(コピペ二重管理を回避)。
    `detectLiveStall(events, now)`(dual_stall・注意/黄)/`detectNoIncumbent(events, now)`
    (no_incumbent・注意/黄)/`detectHighGapDone(summary)`(high_gap_done・情報/グレー)/
    `computeTTFF(events)`/`primalIntegral(events, ref)`
  - `detectLiveStall`は`collectors/attribution.detect_stalls`(時間グリッド+累積最大補間+レート比較)
    と同じ思想のライブ簡易版: 直近30%(最低20秒)窓の改善レートが全体平均レートの50%未満 かつ
    現在gap≥5%で発火。文言に「ライブ簡易判定。全診断はmk.analyzeで実施。改善はlinearize_product等、
    recipe参照」を明記し、mk.analyzeの部分集合であることを隠さない
  - `no_incumbent`: 経過30秒でincumbentイベント0件。`high_gap_done`: doneイベント受信時gap≥50%
  - 指標タイル: TTFF(最初のincumbentのtime)、Primal Integral(ref=現在のincumbent primal、
    区分定数積分。ライブ中は「暫定」注記、done後はref=最終primalで確定値として再計算)
  - サーバ(`minlpkit/live/server.py`)に`/live_rules.js`ルートを追加してファイルをそのまま配信。
    `live_page.html`は`<script src="/live_rules.js">`で読み込み、Nodeテストも同じファイルを
    `require()`する(実体は1箇所のみ)。hatchlingのwheel同梱を確認済み(`live/live_rules.js`)
  - バナーは重ならず縦積み(`.banners`コンテナ)、右端✕で個別非表示(run切替でリセット)。
    比較モードでは非表示(`enterCompareMode`でクリア)
  - **Node単体テスト**(`tests/js/live_rules.test.js`、素のassert・11アサーション):
    (a)序盤急改善→後半フラット+gap大→stall検出、(b)一定レート改善継続→非検出、
    (c)gap低ければ停滞でも非発火(gap閾値の健全性)、(d)incumbentなし30秒→no_incumbent検出、
    (e)incumbent有り/30秒未満→非検出、(f)high_gap_doneの閾値境界、(g)TTFF、
    (h)(i)Primal Integralの階段列手計算一致(2段・3段)、(j)退化入力→0。`node tests/js/live_rules.test.js`
    exit 0で全パス
  - **実データ検証**: `experiments/run_monitor.py --model plant --time 45`を実行しつつ
    `/api/runs/<id>/events`のスナップショット(826イベント、gap 105.8%)にnodeで`detectLiveStall`を
    適用し、実際にplantでstall判定(windowRate 0.514 < 0.5×overallRate 1.712、gap≥5%)になることを確認。
    `detectHighGapDone`もgap 105.8%≥50%で発火を確認
  - 検証: `node tests/js/live_rules.test.js`(exit 0)/ サーバ起動して`/`・`/live_rules.js`が200 /
    上記実データ確認 / `pytest -q`18本パス / `mkdocs build --strict` exit 0
- [x] **C3: スイープ実行 + rerun**(Sonnet): `minlpkit.live.sweep(build_fn, param_sets, name=, time_limit=,
  runs_root=)`(`mk.sweep`としても遅延importで利用可)を追加。設計の要:
  **スイープの各メンバーは通常のrunとして`results/runs/`に記録される**(`solve_with_monitor`の
  既定`capture=True`のまま)。これによりC2のruns一覧UI(チェックボックス比較)がそのまま
  スイープ結果の比較UIになる(専用UIを作らない)。各runの`meta.json`に
  `sweep: {name, index, param_set}`を`update_meta`で追記。返り値は1セット1行の
  DataFrame(index/param_set(str)/run_id/final_dual/final_gap/nodes/time/status)。進捗をprint。
  - `minlpkit.live.rerun(build_fn, run_id, runs_root=, time_limit=)`: 指定runの
    `meta.capture.scip_params_diff`を読み出し、build_fn()の新モデルに適用して再求解。
    新runとして記録し`meta.rerun_of`に元run_idを残す。captureが無い旧run/偽runは
    ValueError(明確なメッセージ)、run自体が無ければFileNotFoundError。
  - `new_run_id`が秒精度のため高速な連続呼び出し(スイープ複数セット)が衝突しうる問題を
    `_unique_run_id`(既存ディレクトリと重ならないよう連番サフィックス)で解消
  - 頂上API: `minlpkit/__init__.py`に`sweep`/`rerun`を`__getattr__`(PEP 562)で遅延export。
    コアの`import minlpkit`はflask/plotly無しで動き続け、`mk.sweep`/`mk.rerun`に実際アクセス
    したときだけ`minlpkit.live`(要viz extras)を読み込む
  - `experiments/run_sweep.py`(CLI): `--model {uc|sched|plant} --time N --config <yaml>`。
    `--config`省略時は組み込みデモ(separating/heuristics強度を変える4セット。
    viz/tune.pyの知見「固定時間はseparating=fast寄りが双対境界を押す」を参考にした構成)。
    yaml読込は環境に既存のPyYAMLを流用(コア依存には追加せず、CLIのみで`import yaml`)。
    結果DataFrame表示 + parallel coordinates図(plotly, パラメータ軸+final_dual/final_gap軸、
    色=final_gap)を`results/sweep.html`に出力(`results/_sweep.png`で目視確認)
  - テスト`tests/test_sweep.py`(4本、実SCIP): sweepが2run記録・meta.sweep正しい/
    rerunのcaptureが元のscip_params_diffを含む(limits除く)・meta.rerun_of正しい/
    captureなし偽runへのrerunがValueError/存在しないrun_idがFileNotFoundError
  - 検証: pytest 22本(既存18+新規4)全パス、doctest(sweep/rerun、実SCIP実行、
    print出力はredirect_stdoutで抑制)全パス、`mkdocs build --strict` exit 0、
    `run_sweep.py --model sched --time 6`実行→4run生成・sweep.html/PNG目視確認、
    サーバ起動して`/api/runs`に4run反映・`/api/runs/<id>/events`のmetaに
    sweep/captureキーを確認、`mk.rerun`を実runに対して実行し新run生成を確認

## Phase 10.1: 導線改修(ギャラリーリンク整理 + レポート一覧 + 設定diff)— 完了

ユーザーストーリー: 自分のプロジェクトで `minlpkit.live.server` を使うと `results/index.html`
(ドキュメント同梱の成果物ギャラリー)は存在せずヘッダの「成果物ギャラリー」リンクが常にリンク切れになる、
かつ試行ループ(runの比較・改善)には無関係の素材だった。ギャラリーは
`docs/`(公開サイト https://ctenopoma.github.io/minlpkit/)専属の役割と割り切り、ライブ側からは撤去して
代わりに「今出力されている静的レポートを開く」「比較runの設定差分を見る」の2機能を追加した。

- [x] ヘッダの「成果物ギャラリー」リンクを撤去し、`GET /api/reports`(`minlpkit/live/server.py`。
  `results/` 直下の `*.html` を name/mtime(ISO)/size で mtime降順に返す。`runs/` は除外、
  空/不在でも200+空リスト)を新設。ヘッダに「レポート」ドロップダウン(`live_page.html`)を追加し
  クリックで `/results/<name>` を新規タブで開く(空時は案内文言)。ヘッダ右端に公開ドキュメント
  (https://ctenopoma.github.io/minlpkit/)への「?」リンクを追加
- [x] 比較モード(2〜8run)に「設定の差分」テーブルを追加。行=パラメータ名(params: time_limit/gap_limit /
  fingerprint: n_vars・n_conss・n_nonlinear / scip_params_diffキーの和集合)、列=選択run(系列色ドット付き)。
  行組み立ては純関数 `buildSettingsDiff`(`minlpkit/live/live_rules.js`。既存の
  detectLiveStall等と同じ「ブラウザ/Node共有の唯一の実体」方針を踏襲)に切り出し、描画は`live_page.html`側。
  値が異なる行は淡黄背景で強調(既定ON、「差分がある行のみ表示」トグルでOFF可)。capture無し旧runの列は
  「記録なし」。データは比較モードが既に取得済みの `/api/runs/<id>/events` の meta を再利用(追加fetch無し)
  - 検証: `tests/js/settings_diff.test.js`(Node、素のassert、実runの `/api/runs/<id>/events` スナップショットで
    `separating/maxroundsroot` の差分検出を実データ確認済み)、`tests/test_server.py`(pytest、Flask test client、
    `/api/reports` がresults/直下のhtml集合と一致・mtime降順・空/不在時200、`/` にレポート/diffpanel要素が
    含まれギャラリーリンクが無いことを確認)。pytest 25本(既存22+新規3)全パス、
    `mkdocs build --strict` exit 0、node構文チェック(埋め込み script + live_rules.js)OK、
    サーバ起動して `/`・`/api/reports`(30本のresults直下html)・`/api/runs`・`/live_rules.js` が200

## Phase 11: GPU対応(cuOpt × SCIP ハイブリッド)— 着手 2026-07-19

従来「実機なし」を理由に除外していたGPU(ノート [[cuOpt_MILP_beta]] の技術)を、
実機確認(RTX 5070 Ti 16GB / CUDA 13.1 / WSL2 Ubuntu 稼働中)を受けて解禁。
cuOptはLinux専用だが**WSL2が公式サポート**("WSL2 is tested to run cuOpt")のため、
Windows母艦+WSL2の2プロセス構成で「GPU=可行解探索、CPU(SCIP)=証明」の分業を実証する。

- [x] **11.1 cuOpt 25.10 導入**: WSL2 Ubuntu に uv venv(Python 3.12)+ `cuopt-cu13==25.10.*`
  (`--extra-index-url=https://pypi.nvidia.com`、venv: `~/cuopt-env`)。`cuopt_cli` が
  RTX 5070 Ti を認識し GAP small を求解できることを確認
- [x] **11.2 GPU向き対象問題の追加**: 既存サンプルは小規模MINLP(cuOptはMILP専用)のため、
  文献(cuOpt論文 arXiv:2510.20499、Feasibility Jump論文=MIP 2022優勝)でGPU primal
  heuristicsが効くとされる「可行解発見が難しい大規模MILP」を新規作成
  - `samples/gap_large.py` — タイト容量の一般化割当(Yagiura タイプD類似、small/large/xl、最大24万バイナリ)
  - `samples/set_partitioning.py` — 集合分割(植え込み解で可行性保証、最大10万列)
- [x] **11.3 3アーム比較実験** `experiments/run_gpu_heuristic.py`(scip / cuopt / hybrid):
  PySCIPOptでMPS出力 → WSLの`cuopt_cli`で求解 → `.sol`(SCIP互換形式)を `readSolFile`+`addSol`
  でSCIPにwarm start注入。incumbent軌跡はEventhdlr(SCIP)とログparse(cuOpt)で記録、
  `results/gpu/<tag>_compare.csv` に出力
  - **GAP large(75,000バイナリ、60s)**: 純SCIP gap 22.9%(解3個)/ cuOpt(GPU)gap **0.64%** /
    hybrid(cuOpt 15s注入→SCIP)gap 4.72% — GPUヒューリスティクスの圧勝。ノートの
    「効く局面=初期可行解が見つかりにくい大規模MILP」を実測で確認
  - **集合分割 large(40,000列、60s)**: cuOptはルートLP(双対シンプレックス、CPU側)が退化で
    60秒を使い切りGPUヒューリスティクス未到達。`--mip-heuristics-only` でも可行解なし。
    純SCIPは2解(21,584)発見 — **等式制約系はFJ系が苦手**という文献どおりの負の結果(FINDINGS参照)
- [x] **11.4 ライブラリAPI化 `mk.cuopt_warmstart`**(`minlpkit/gpu.py`、Sonnet委譲):
  「MPS書き出し→WSLのcuopt_cli→.sol注入」を1関数に。可行解なし時のゼロ埋め.solは注入
  スキップ。ネイティブLinux用に `cuopt_cmd` 差し替え可。実GPUで回る `tests/test_gpu.py` 付き。
  `docs/manual.md` 7節に導入・使用例。run_gpu_heuristic.py のhybridアームもこれを使う形にリファクタ
- [x] **11.5 診断ルール `gpu_primal`**: 観測量に `nsols`/`ttff`(BESTSOLFOUNDイベントで計測)/
  `solve_time`/`has_nonlinear`/`n_bin_vars`/`eq_share`/`eq_overlap` を追加し、
  「大規模線形バイナリ+可行解僅少+gap残存 → mk.cuopt_warmstart 推薦」をRULESに追加。
  GAP large実走で発火をE2E確認。**判別知見**: 等式の比率では判別不能(GAPも等式95%でcuOpt圧勝)。
  正しい判別子は等式同士の変数共有度 `eq_overlap`(GAP 1.0 / 集合分割 10.1、閾値1.5)
- [x] **11.6 GPU比較ダッシュボード** `experiments/gpu_dashboard.py`(Sonnet委譲):
  `results/gpu/*_compare.csv` → incumbent階段チャート+TTFF/最終best/Primal Integralタイル
  のHTML。可行解なしアームは明示表示。dataviz規範準拠(CVD検証済みパレット、plotly.jsオフライン埋め込み)
- [x] **11.7 ライブモニタ統合**(Sonnet委譲): run_gpu_heuristic.py に `--live`。
  各アームを `results/runs/` の1runとして記録(scip/hybrid=solve_with_monitor経由で
  capture付き、cuopt=parse済み軌跡のバッチ書き込み、注入解はt=0イベント)。
  ライブUI比較モードでアーム間比較と設定diff(arm/scale/gpu_budget)が見られる
- [x] **11.8 常駐型ハイブリッド `mk.cuopt_concurrent`**: cuOptをPopenでSCIPと並走させ、
  終了し次第イベントハンドラ(NODESOLVED+LPSOLVED)から `createSol`+`trySol` でmid-solve注入。
  GPU待ちの直列時間ゼロ(hybrid 77s→concurrent 60sで同一解)。9p I/O(MPS読み+20s/.sol書き+19s)を
  WSLネイティブ/tmpステージングで回避、`num_cpu_threads` でCPU競合制御。
  実験は concurrent アーム(既定armsに追加)、テストは test_gpu.py::test_cuopt_concurrent_injects_during_solve
- 将来拡張候補: cuPDLP(LP側のGPU一次法)の検証(→11.9で実施)、xlスケール実験(→11.10)

## スコープ外

- **ML/GNN系(Forge、学習分岐等)・LLM支援**: 基盤の導入可否判断が必要なため当面除外。診断ルール表の将来拡張候補として名前だけ残す
- ~~GPU(cuOpt等)~~ → **Phase 11で解禁**(実機RTX 5070 Ti + WSL2でcuOpt導入済み)
- Pyomo、量子(QUBO/イジング、専用ハード前提)
- ※ MDDは非ML/GPU/LLMのため上記監査の❌に移動(スコープ外ではなく「やり残し」)
