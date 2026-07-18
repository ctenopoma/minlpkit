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
uv run python -m viz.server
# 書き手(何度でも。新しいrunは自動でUIに現れる)
uv run python experiments/run_monitor.py --model plant --time 120
```

ブラウザは最新runを自動選択しSSEで購読、`summary.json` 出現で `done` を受けて確定表示。
複数runはドロップダウンで切替(Phase 4のbefore/after比較の土台)。
「比較モード」チェックボックスで2runを選ぶと、`/api/runs/<id>/events`(全イベント一括取得)から
双対/primal境界とgapを1チャートに重ね描画できる(run A=青、run B=オレンジ、凡例にrun名。before/after検証用)。

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
