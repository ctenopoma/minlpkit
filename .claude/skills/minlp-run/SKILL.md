---
name: minlp-run
description: MINLPサンプルモデルの標準実行手順。モデルの実行・モニタ付き求解・出力先の規約。
---

# minlp-run: サンプルモデルの標準実行手順

## 実行コマンド

- 単体実行(コンソール出力のみ): `uv run python samples/<model>.py`
- **モニタ付き実行(推奨・書き手)**: `uv run python experiments/run_monitor.py --model {uc|sched|plant} --time <秒> --gap <比率>`
  - 出力: `results/<model>_dashboard.html`(静的)+ `results/runs/<run_id>/`(ライブ用ログ)
- **ライブ表示(読み手)**: 別ターミナルで `uv run python -m viz.server` → http://127.0.0.1:5000
  - 読み手は開きっぱなしで良い。書き手を実行するたび新しいrunがUIに自動で現れる
- 日本語出力の文字化け防止: 先に `$env:PYTHONIOENCODING='utf-8'`

## モデル一覧と特性

| キー | ファイル | 特性 | 推奨時間制限 |
| --- | --- | --- | --- |
| `uc` | samples/scheduling/unit_commitment.py | 4秒/1ノードで解ける(ルート集中型。トラジェクトリは短い) | 60s |
| `sched` | samples/others/scheduling.py | 1秒未満で解ける(ベースライン) | 60s |
| `plant` | samples/others/scheduling_plant.py | gap停滞が観察できる難問(300sでgap72%) | 120-300s |

## 規約

- パッケージは `uv add`(pip / uv pip 禁止)
- 時間制限は `limits/time`、gap制限は `limits/gap`(比率。0.01=1%)
- 新モデル追加時: `samples/` に `build_model() -> Model` を持つ形で置き、
  `experiments/run_monitor.py` の `MODELS` 辞書に登録し、この表にも1行足す

## 既知の制約

- SCIPのクロックはWindowsで1秒粒度 → モニタはPython側wall clock(`perf_counter`)で記録済み
- ヒューリスティクス(サブSCIP)内のイベントは親SCIPに伝播しない → ルート集中型の問題ではログ行数が少ない
