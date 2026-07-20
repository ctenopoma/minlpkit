# MIP/MINLP キャッチアップ用リポジトリ

MINLPの最新動向キャッチアップを目的とした実験リポジトリ。
題材ノート: `C:\Users\naoki\OneDrive\デフォルト\ドキュメント\obsidian\Optimization\Mixed Integer Programming.md`
計画: `task.md`、調査結果(開発中に判明した非自明な事実): `FINDINGS.md` を参照。

## 作業方針(厳守)

- **勝手にスキップ・保留・「対象外」判断をしない。** タスクは完遂する。
- **仮実装・スタブ・モックで済ませない。** 実データ・実ソルバーで動く本実装のみ。
- **サンプル問題で確認できないなら、確認できる問題を自分で作って検証してから進める。**
  「このモデルでは条件が揃わないので対象外」は禁止。条件が揃うモデルを新規作成して確認する。
- スキップ・割り切りが本当に必要と考える場合は、勝手に決めずユーザーに確認する。

## パッケージ管理ルール(厳守)

- **uv を使う。pip / uv pip は使わない。**
  - 依存追加: `uv add <pkg>`(dev依存は `uv add --dev <pkg>`)
  - 実行: `uv run python <script>`(コンソールで日本語が化ける場合は `$env:PYTHONIOENCODING='utf-8'` を先に設定)
  - 削除: `uv remove <pkg>`
- Pyomoは使わない。モデリングは **PySCIPOpt** に統一する。

## 技術スタック

- Python 3.12(uv管理、`.venv`)
- PySCIPOpt(SCIPバンドル済み。MINLPを空間分枝限定法で厳密求解)
- pandas + plotly(ログ構造化・可視化)

## SKILLs管理

このプロジェクトで使う/作るスキルの一覧。自作スキルは `.claude/skills/<name>/SKILL.md` に置く。

### 利用する既存スキル(OSS/組み込み)

| スキル | 用途 | 使うタイミング |
| --- | --- | --- |
| `dataviz` | チャート/ダッシュボードのデザイン規範 | Plotly等でグラフを描く前に必ずロード |
| `verify` | 変更のend-to-end動作確認 | モデル/可視化コードの変更をコミットする前 |
| `code-review` | diffのバグ・簡素化レビュー | フェーズ完了時 |

### 自作スキル(`.claude/skills/`)

| スキル | 状態 | 用途 |
| --- | --- | --- |
| `minlp-run` | 作成済 | サンプルモデルの標準実行手順(run_monitor.py、出力先規約、既知の制約) |
| `minlp-viz` | 作成済 | Eventhdlrログ→Plotlyダッシュボード生成の定型手順とデザイン規約 |
| `minlp-diagnose` | 作成済 | 診断ルール表(観測量→症状→改善提案)と健全性ルール。`run_diagnose.py`の使い方 |

## 可視化アーキテクチャ(TensorBoard型: 書き手/読み手分離)

- **書き手**: `run_monitor.py`(ソルバー)が `results/runs/<run_id>/` にログを追記
- **読み手**: `uv run python -m minlpkit.live.server`(Flask+SSE)がそれを tail してブラウザへライブpush(後方互換で `python -m viz.server` も可)
- 2コマンド運用(train.py + tensorboard と同型)。ライブ表示は http://127.0.0.1:5000
- 詳細は `minlp-viz` スキル参照

## minlpkit(Phase 5: 統合ライブラリ)

Phase 1-4を一体化したmodel非依存のパイプライン。`import minlpkit as mk`:
- `mk.analyze(build_fn, name, time_limit, interval_terms_fn)` → `Report`(観測量+診断)
- `report.summary()` / `report.dashboard(path)`(統合HTML)
- `mk.compare_variants({name: build_fn})` → before/after比較DataFrame(ルート双対境界・gap・ノード)
- `mk.RULES` / `mk.evaluate`(診断ルール。プラガブル: RULESにRuleを追加可能)
- 一気通貫デモ: `uv run python demo.py`(可視化→診断→改善→再検証)

## ディレクトリ構成

- `samples/` — MINLPサンプルモデル(unit commitment、スケジューリング、facility、knapsack、cutting_stock等)
- `minlpkit/` — **単体で成立する配布パッケージ**(別プロジェクトから `uv add --editable` で導入可)。
  - `pipeline.py`/`compare.py`/`render.py`/`transforms.py`/`frameworks.py` — 統合API
  - `collectors/` — 観測量収集器・診断ルールの**実体**(diagnose/attribution/tree/static_diag/symmetry/violation)。
    Phase 1-4 の収集器をここへ移設し、minlpkit は viz に依存しなくなった
  - `live/` — ライブ可視化の**実体**(monitor/run_logger/server/plots/live_page.html)。**extras `viz`**(flask/plotly/kaleido)。
    起動: `python -m minlpkit.live.server`。extras未導入で `import minlpkit.live` すると案内付きImportError
  - `tune.py` — SCIPパラメータ自動チューニングの**実体**。**extras `tune`**(optuna)
  - **コア**の実行時依存は pyscipopt/pandas/numpy/scipy のみ(`[project.dependencies]`)。extras は
    `[project.optional-dependencies]` の `viz`/`tune`。ビルドは hatchling、wheel対象は minlpkit(live/live_page.html 同梱)
- `viz/` — **後方互換シム専用**。収集器6本は `minlpkit.collectors` へ、
  monitor/run_logger/server/plots は `minlpkit.live` へ、tune は `minlpkit.tune` へ転送
  (`from minlpkit.X import *` + `__getattr__`)。`python -m viz.server` も引き続き起動可。
  実体を持つのは mccormick/plant_terms/interval/bottleneck/colgen/benders/attribution等の残置分のみ
- `experiments/run_*.py` — 各機能の調査用CLI(monitor/tree/attribution/violation/bottleneck/static_diag/
  interval/symmetry/diagnose/improve_*/colgen/stabilize/benders/bnp/sos/condition/perspective/tune/
  gpu_heuristic=cuOpt(WSL2/GPU)×SCIPハイブリッド)。
  実行は `uv run python experiments/run_<name>.py ...`(出力は `results/` へ)
- `demo.py` — minlpkit一気通貫デモ(ルート残置のクイックスタート)
- `docs/` — 利用マニュアル(`manual.md`)+ MkDocs(`mkdocs.yml`)。`uv run mkdocs serve` でAPIリファレンス閲覧
- `tests/` — pytest(実SCIPで回すtransforms/frameworks/diagnose/pipelineのテスト。`uv run pytest`)
- `README.md` — プロジェクト概要とクイックスタート
- `task.md` — 取り組みプランと進捗、`FINDINGS.md` — 調査知見

## ドキュメント(MkDocs)の知見

ドキュメントサイト(`docs/`, `mkdocs.yml`)は、MkDocs MaterialをベースにモダンなUXを提供するための設定が行われている。

- **Zenn風 Admonition**: `extra.css` にて、デフォルトの太い左線を消し、パステル背景＋アイコンのフラットデザインに上書き。
- **Mermaid**: `pymdownx.superfences` の `custom_fences` に `!!python/name:pymdownx.superfences.fence_code_format` を指定することで、MkDocs Material組み込みのMermaidレンダラーを安全に起動できる。(`fence_mermaid_format` はモジュールエラーになるため不可)。
- **Draw.io**: `mkdocs-drawio` プラグインを使用し、`![図](...drawio)` でインライン描画。
- **Lightbox**: `mkdocs-glightbox` プラグインを使用し、画像のクリック拡大を有効化。
- **最終更新日**: `mkdocs-git-revision-date-localized-plugin` プラグインを使用し、Gitのコミットから更新日時を自動付与。
- **変数マクロ**: `mkdocs-macros-plugin` プラグインを使用し、`mkdocs.yml` の `extra` で定義した変数(例: `{{ minlpkit_version }}`)をMarkdown内に埋め込み可能。
  - ※注意: `macros` を有効にすると Jinja2 構文が有効になるため、MkDocsの `attr_list` 用の見出しID `{#id-name}` が「Jinja2の未終端コメント」と解釈されて構文エラーになる。これを回避するため、見出しIDには必ずスペースを入れた `{: #id-name }` を使用すること。
