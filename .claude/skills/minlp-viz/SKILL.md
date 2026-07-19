---
name: minlp-viz
description: SCIP探索ログのPlotlyダッシュボード生成手順。Eventhdlrログ収集と可視化の定型フロー・デザイン規約。
---

# minlp-viz: 収束ログ可視化の定型手順

## 統合API(Phase 5)

`import minlpkit as mk` で Phase 1-4 を一体利用:
`mk.analyze(build_fn) → Report`、`Report.dashboard(path)`、`mk.compare_variants({name: build_fn})`。
個別の可視化は下記の `experiments/run_*.py` / `viz/` を直接使う。`demo.py` が一気通貫デモ。

## 構成

書き手(ソルバー)と読み手(UIサーバ)を **run ディレクトリのファイルのみで分離**する
TensorBoard型アーキテクチャ。ライブ表示もバッチ出力も同じログから作る。

- `viz/run_logger.py` — `RunLogger`(SummaryWriter相当)。`results/runs/<run_id>/` に
  `meta.json`(開始時)/ `events.jsonl`(逐次追記)/ `summary.json`(終了時)を書く
- `viz/monitor.py` — `SolveMonitor`(Eventhdlr)。BESTSOLFOUND / NODESOLVED / LPSOLVED を
  捕捉。`logger` を渡すと逐次追記もする。`solve_with_monitor()` で求解、`primal_gap_series()` でPrimal Integral
- `viz/server.py` — **読み手**。Flask + SSE。`events.jsonl` を tail してブラウザにライブpush。
  plotly.js はオフライン配信(`get_plotlyjs()`、CDN不要)。`viz/live_page.html` がフロント
- `viz/plots.py` — バッチ用の静的Plotly図と `build_dashboard()`(単一HTML)
- `experiments/run_monitor.py` — **書き手**。求解して run ディレクトリ + 静的ダッシュボードを出力
- `viz/mccormick.py` + `experiments/run_mccormick.py` — Phase 2.a。McCormick凸緩和の締まりの3Dアニメ
  (`results/mccormick.html`)。ソルバー不要の解析的可視化
- `viz/tree.py` + `experiments/run_tree.py` — Phase 2.a。空間分枝木(`results/tree.html`)。分枝変数の型で
  spatial(連続)/integer/binary を色分け
- `viz/attribution.py` + `experiments/run_attribution.py` — Phase 2.a。双対境界改善の分枝への帰属
  (`results/attribution.html`)。Phase1(双対推移)×Phase2(分枝変数)の結合。停滞はレートベース検出
- `viz/violation.py` + `experiments/run_violation.py` — Phase 2.b。非線形制約の違反量ヒートマップ
  (`results/violation.html`)。ルートLP緩和解の相対違反で支配的ボトルネック制約を特定
- `viz/bottleneck.py` + `experiments/run_bottleneck.py` + `samples/facility.py` — Phase 2.b。線形制約の
  スラック/影の価格ボトルネックとIIS(削除フィルタ法)。`results/bottleneck.html`
  - 純粋線形の検証用モデルが必要な診断は `facility.py`(容量制約付き施設配置MILP)を使う
  - `getDualsolLinear(cons)`=LP影の価格。IISは build_fn(active集合)でモデル再構築する削除フィルタ
- `viz/static_diag.py` + `experiments/run_static_diag.py` — Phase 2.c。静的診断(solve前)。係数スケール/Big-M検出、
  制約-変数の接続行列(RCM並べ替え)とブロック/結合制約。`results/static_<model>.html`
  - 係数抽出: 線形制約は`getValsLinear`(**キーは変数名の文字列**)、RHS/LHSは`getRhs/getLhs`、目的は`v.getObj()`、境界は`getLb/UbGlobal`
  - 接続行列は`getConsVars`(非線形制約でも動く)。RCM並べ替えはscipyの`reverse_cuthill_mckee`
  - 変数名は`v.name`(`getName()`は無い)。診断は現れるモデルで検証(Big-M=uc、構造=plant)
- `viz/interval.py` + `viz/plant_terms.py` + `experiments/run_interval.py` — Phase 2.c。区間演算で非線形項の値域を
  静的に見積もる(`results/interval.html`)。実Intervalクラス(+,-,*,/,exp,pow)。緩和の緩さを事前予測
- `viz/symmetry.py` + `experiments/run_symmetry.py` + `samples/parallel_machines.py` — Phase 2.c。対称性検出。
  1-hop color refinement(制約形状+自身係数のシグネチャ)。`results/symmetry.html`。対称性の検証には
  恒等並列機械モデルを使う(facilityは対称性なしの対照)。境界の無限は±infにしてシグネチャをソート可能に

## 非線形制約の違反量取得(violation.py で判明)

- ルートLP緩和解: `FIRSTLPSOLVED`イベント + `limits/nodes=1`。`createSol()`に各変数の`getLPSol()`を入れる
- 非線形制約の違反: `getNlRowSolFeasibility(nlrow, sol)`(負=違反量)。`getSlack`は非線形非対応でWarning
- NlRowは制約名を保持(`nr.name`)。名前を`rpartition("_")`で (タイプ, エンティティ) に分解できる
- 違反はスケール差が桁違い → 相対違反 = 違反量/(|活動値|+1) で正規化してから比較・描画する

## SCIP分枝ノード収集の注意(tree.py で判明)

- 分枝ノードは **`NODEBRANCHED`** で捕捉(`NODEFOCUSED`だと`getParentBranchings()`が空)
- 分枝は**変換後変数**(`t_`接頭辞)に対して起きる。変数型は分枝が返す変数オブジェクトの
  `.vtype()` で取る(元変数名でvtype辞書を引くと名前不一致で全部Noneになる)
- `getParentBranchings()` → `(vars, bounds, boundtypes)`。boundtype 1=`<=`(上界), それ以外=`>=`
- 連続変数(CONTINUOUS)への分枝 = 空間分枝 = MINLP固有。ここを青(slot1)で強調する

## 3D図(Surface)の注意

- 3Dはカメラ角度依存で読みにくい。**必ずPNG出力して目視調整**してからHTML確定する
- z=x·y 等の鞍型は**対称box**にすると形が読みやすい。`aspectmode="cube"`、
  カメラ `eye≈(1.6,1.6,1.15)` が良かった(mccormick.py参照)
- 真の曲面=グレー半透明、緩和=series-1青。単一hueのcolorscaleでベタ塗り

## ライブ表示の使い方(train.py + tensorboard と同じ2コマンド)

```
# 読み手(1回起動して開きっぱなし): http://127.0.0.1:5000
uv run python -m minlpkit.live.server   # 後方互換: uv run python -m viz.server も同じ
# 書き手(何度でも。新しいrunは自動でUIに現れる)
uv run python experiments/run_monitor.py --model plant --time 120
```

### UI構成(Phase 10 C2+A: TensorBoard型2ペイン)

- **左サイドバー(runs一覧テーブル)**: モデル名/開始時刻/status/gap/nodes列。
  列ヘッダクリックでソート、上部のテキスト入力でモデル名/status部分一致フィルタ。
  `/api/runs` を5秒間隔でポーリングして再描画(進行中runのgap/nodesもライブ更新)
- **行クリック=単一run表示**: 従来通りSSE購読(`/api/runs/<id>/stream`)でライブ更新、
  `summary.json` 出現で `done` を受けて確定表示。最新runを自動選択
- **チェックボックス=比較選択(2〜8run)**: チェックした順に固定パレット
  `["#2a78d6","#008300","#e87ba4","#eda100","#1baf7a","#eb6834","#4a3aa7","#e34948"]`
  を割り当てて重ね描き(dual=実線/primal=点線、gapも重ね描き)。9run目以降は選択不可(チェックボックスdisabled)
  データ取得は選択run分だけ `/api/runs/<id>/events`(全イベント一括)を並列fetch
- **run詳細(折りたたみ)**: 単一run表示時のみ、`meta.capture`(C1でキャプチャ)を表示。
  scip_params_diff(表)・fingerprint(変数/制約内訳)・env・git_sha。captureが無い旧runは「記録なし」
- サーバの `/api/runs` は容量削減のため `capture` をフルで返さず要約
  `capture_summary`(n_params_diff・fingerprintの変数/制約内訳・git_sha短縮)に差し替える。
  フルcaptureは `/api/runs/<id>/events` のmetaにある

### ライブ診断・ライブ指標(Phase 10 B)

- 単一run表示時、症状バナー+ライブ指標タイルが出る。判定関数の実体は `minlpkit/live/live_rules.js`
  1箇所のみ(サーバが`/live_rules.js`で配信、`live_page.html`が`<script src>`で読み、
  Nodeテスト`tests/js/live_rules.test.js`が同じファイルを`require()`する。コピペ二重管理は禁止)
- `detectLiveStall(events, now)`: `collectors/attribution.detect_stalls`と同じ思想のライブ簡易版。
  直近30%(最低20秒)窓の双対改善レートが全体平均の50%未満 かつ 現在gap≥5%で発火(dual_stall・黄)。
  `detectNoIncumbent`: 経過30秒でincumbent0件(黄)。`detectHighGapDone`: done時gap≥50%(グレー・情報)
- **正直な設計原則**: ここで評価できるのは`mk.RULES`(6ルール)の一部の簡易ライブ版のみ。
  バナー文言に必ず「全診断はmk.analyzeで実施」の1行を含める。ライブ判定を全診断の代替として謳わない
- ライブ指標: TTFF(`computeTTFF`、最初のincumbentのtime)、Primal Integral(`primalIntegral`、
  ref=現在のincumbent primal、区分定数積分。ライブ中は「暫定」表示、done後はref=最終primalで確定再計算)
- 比較モードではバナーを表示しない(単一run特有の機能)。新しい判定ルールを足すときは
  `live_rules.js`に純関数を追加し、`tests/js/live_rules.test.js`に合成イベント列のテストを足す

### スイープ実行・rerun(Phase 10 C3)

`minlpkit/live/sweep.py`(`sweep`/`rerun`。`mk.sweep`/`mk.rerun`としても`minlpkit/__init__.py`の
`__getattr__`で遅延import可、コアimportにflask/plotlyを強制しない)。設計の要:
**スイープの各メンバーは通常のrunとして`results/runs/`に記録される**(`solve_with_monitor`の
既定`capture=True`のまま)ので、C2のruns一覧UI(チェックボックス比較)がそのままスイープ比較UIになる
(専用UI不要)。各runの`meta.json`に`sweep: {name, index, param_set}`を追記。`rerun`は
`meta.capture.scip_params_diff`を読み出して同じ`build_fn`の新モデルへ適用・再求解し、
`meta.rerun_of`に元run_idを残す(captureが無い旧runはValueErrorで明確に失敗)。
CLI `experiments/run_sweep.py --model sched --time 6`(`--config <yaml>`でカスタムparam_sets、
PyYAMLはCLI内のみ使用しコア依存には追加しない)がsweep結果とparallel coordinates図
(`results/sweep.html`)を出力する。`new_run_id`の秒精度衝突は`_unique_run_id`で回避。

## デザイン規約(dataviz スキル準拠)

- **チャートを書く前に必ず `dataviz` スキルをロードする**
- 色は `viz/plots.py` の `C` 辞書(検証済み参照パレット)から取る。slot1青=primal系、slot2緑=dual系で固定。系列色の使い回し・新規hex追加はしない
- 1チャート1軸(二重軸禁止)。2系列以上は凡例必須。ホバーは `hovermode="x unified"`
- ローカル分析用HTMLはライトテーマ固定(意図的な選択)

## 図を追加するとき

1. `viz/plots.py` に `fig_xxx(df) -> go.Figure` を追加(`_base_layout()` を使う)
2. `build_dashboard()` の `figs` リストに足す
3. kaleidoでPNG出力して目視確認: `fig.write_image(...)` → Readツールで見る

## 指標の定義

- gap: SCIPの `getGap()`(比率)。対数プロットは0を除外してから描く
- Primal gap p(t) = |primal(t) − ref| / max(|primal|, |ref|)、ref=最終primal(Achterberg流)
- Primal Integral = ∫p(t)dt(区分定数近似)。小さいほど「早く良い解に到達」
