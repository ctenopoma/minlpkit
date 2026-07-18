# minlpkit

MINLP(混合整数非線形計画)の **可視化 → 診断 → 改善 → 検証** を PySCIPOpt(SCIP)上で
一体化したツールキット。求解プロセスをモニタして「症状」を観測し、診断ルールで
「どの改善が向くか」を推薦し、再定式化ヘルパー/アルゴリズムフレームワークで改善を実施し、
before/after を比較検証するまでを1つのライブラリで通す。

**設計思想は SCIP-aware**: 現代の SCIP が presolve / 分離 / 対称性処理 / 被約コスト固定などで
**自動でやってしまうこと**は推薦しない(手動でやっても無効〜悪化するため)。診断が推すのは、
SCIP が自動ではやらない「整数構造を突いた厳密線形化」「分解(ベンダーズ/列生成)」など、
非凸緩和の弱さに効く定式化の作り込みだけ。根拠は実測で `FINDINGS.md` にまとめてある。

## ディレクトリ構成

```
mip/
├── minlpkit/            単体で成立する配布パッケージ (uv add --editable で外部導入可)
│   ├── pipeline.py        analyze / collect_metrics / Report
│   ├── compare.py         compare_variants(before/after比較)
│   ├── transforms.py      linearize_product / pwl_sos2 / perspective_quadratic
│   ├── frameworks.py      column_generation / price_and_branch / benders
│   ├── render.py          統合ダッシュボードHTML描画
│   ├── tune.py            SCIPパラメータ自動チューニング(extras: minlpkit[tune])
│   ├── collectors/        観測量収集器・診断ルールの実体(diagnose ほか6本)
│   └── live/              ライブ可視化の実体(monitor/run_logger/server/plots/live_page.html。extras: minlpkit[viz])
├── samples/             MINLPサンプルモデル(unit_commitment/scheduling_plant/facility/…)
├── viz/                 後方互換シム(monitor/run_logger/server/plots/tune → minlpkit.live/tune へ転送)
├── experiments/         調査用CLI run_*.py(実行すると results/ にHTMLを出力)
├── results/             成果物HTML + ライブ用 runs/(index.html が成果ギャラリー)
├── docs/                利用マニュアル(manual.md)+ MkDocs(APIリファレンス自動生成)
├── tests/              pytest(実SCIPで回すtransforms/frameworks/diagnose/pipeline)
├── demo.py              一気通貫デモ(クイックスタート用にルート残置)
├── CLAUDE.md / task.md / FINDINGS.md   運用方針・進捗・調査知見
```

> `site/`(MkDocsビルド出力)と `__pycache__/` は生成物であり配布物ではない(`uv run mkdocs build` / 実行のたびに再生成される)。バージョン管理・配布対象に含めない。

## クイックスタート

```powershell
uv sync                               # extras(viz/tune)込みで開発環境を用意
$env:PYTHONIOENCODING = 'utf-8'
uv run python demo.py                 # 可視化→診断→改善→再検証の一気通貫デモ
uv run python -m minlpkit.live.server # ライブモニタ + 成果ギャラリー (http://127.0.0.1:5000)
```

ライブ可視化(`minlpkit.live`)とチューニング(`minlpkit.tune`)は追加依存
(flask/plotly/kaleido、optuna)を要する **extras**。外部プロジェクトでは
`uv add "minlpkit[viz,tune]"` で導入する(コアだけなら extras 不要)。
`python -m viz.server` は後方互換シムとして引き続き起動できる。

`demo.py` は plant モデルを analyze して診断を表示し、推薦(n·s の厳密線形化)を適用して
`compare_variants` で before/after を出す(ルート双対境界 52→133、gap を大幅圧縮)。
`minlpkit.live.server` は別ターミナルの `experiments/run_monitor.py` が書くログを tail して
ライブ配信し、`results/index.html` の成果ギャラリーも配信する。

## 主要 API(`import minlpkit as mk`)

| API | 役割 |
| --- | --- |
| `mk.analyze(build_fn, name, time_limit, ...)` | 観測量収集 + 診断 → `Report`(`.summary()` / `.dashboard(path)`) |
| `mk.compare_variants({名前: build_fn}, time_limit)` | 改善の before/after(ルート双対境界・gap・ノード)を1表に |
| `mk.linearize_product(m, y, x, y_lb, y_ub, x_lb, x_ub, name)` | 整数×連続の積 y·x を厳密線形化(McCormickギャップ0) |
| `mk.pwl_sos2(m, x, breakpoints, values, name)` | 1変数関数を SOS2 で区分線形近似(Big-M不要) |
| `mk.benders(master_build, subproblem_solve)` | ベンダーズ分解(コールバック方式の汎用ドライバ) |
| `mk.column_generation(rhs, init_columns, pricing_fn, alpha)` | 列生成(Gilmore-Gomory / Wentges安定化) |
| `mk.price_and_branch(rhs, init_columns, pricing_fn)` | 列生成 + 整数主問題(branch-and-price、整数解は上界) |

## 別プロジェクトからの導入

`minlpkit` は単体で成立する配布パッケージ(コアの実行時依存は pyscipopt/pandas/numpy/scipy のみ)。
外部プロジェクトから editable 導入できる:

```powershell
uv add --editable C:\work_space\mip                              # コアのみ(依存4つ)
uv add "minlpkit[viz,tune] @ file:///C:/work_space/mip"          # + ライブ可視化 / チューニング
```

コアだけなら `import minlpkit` が extras 無しで動く。`minlpkit.live`(flask/plotly/kaleido)や
`minlpkit.tune`(optuna)を使うときは対応する extras を入れる(未導入なら導入方法を案内する
ImportError が出る)。

```python
import minlpkit as mk
from pyscipopt import Model

def build():
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3); s = m.addVar(lb=0, ub=10)
    ns = mk.linearize_product(m, n, s, 1, 3, 0.0, 10.0, "ns")
    m.addCons(ns >= 12); m.setObjective(n + s, "minimize")
    return m

print(mk.compare_variants({"model": build}, time_limit=5))
```

## ドキュメント

- **利用マニュアル**: [`docs/manual.md`](docs/manual.md) — インストール・ワークフロー・全API・ライブモニタ・診断ルール表・落とし穴
- **APIリファレンス(自動生成)**: `uv run mkdocs serve` → http://127.0.0.1:8000(docstring から生成)
- **調査知見**: [`FINDINGS.md`](FINDINGS.md) — SCIPが自動でやること/測定方法論/効く改善・効かない改善の実測
- **計画と進捗**: [`task.md`](task.md)
- **成果ギャラリー**: `results/index.html`(`minlpkit.live.server` 起動時は `/results/index.html`)
