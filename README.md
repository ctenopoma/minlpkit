# minlpkit

**PySCIPOpt(SCIP)で解くMINLPの「なぜ遅いか」を観測し、直し方を提案するツールキット。**

![Python](https://img.shields.io/badge/python-3.12+-blue.svg)
![PySCIPOpt](https://img.shields.io/badge/solver-PySCIPOpt%20(SCIP)-informational.svg)

求解プロセスをモニタして症状を観測し、診断ルールで「どの改善が効くか」を推薦し、
再定式化ヘルパーやアルゴリズムフレームワークで改善を実施し、before/after を比較検証する
——ここまでを1つのライブラリで通します。

## Features

- 🔍 **診断 (`analyze`)** — 双対境界の停滞・空間分枝の偏り・非線形制約の違反・係数スケール・
  対称性などを収集し、発火した症状を重要度順に返す
- 🛠️ **改善ヘルパー** — 整数×連続の積を厳密線形化する `linearize_product`、Big-M不要の
  区分線形近似 `pwl_sos2` など、非凸緩和の弱さに効く再定式化の部品
- 🧩 **汎用ドライバ** — ベンダーズ分解 (`benders`)、列生成・branch-and-price
  (`column_generation` / `price_and_branch`) をモデルに依存しない形で提供
- ✅ **before/after 検証 (`compare_variants`)** — ルート双対境界・最終gap・ノード数を並べて
  改善の効果を定量比較
- 📡 **ライブモニタ** (`minlpkit[viz]`) — 求解中の双対境界・primal・gapをブラウザにライブ配信
  (TensorBoard型、run比較モードあり)
- ⚙️ **自動チューニング** (`minlpkit[tune]`) — Optunaで SCIP パラメータを探索
- 🔌 **プラガブルな診断ルール** — `mk.RULES` に独自ルールを追加できる

## Installation

```powershell
uv add minlpkit                      # コアのみ(pyscipopt/pandas/numpy/scipy)
uv add "minlpkit[viz,tune]"          # + ライブモニタ / Optunaチューニング
```

ローカルの編集可能インストール:

```powershell
uv add --editable C:\work_space\mip
uv add "minlpkit[viz,tune] @ file:///C:/work_space/mip"
```

## Quickstart

```python
import minlpkit as mk
from pyscipopt import Model

# n·s >= 12 (整数×連続の双線形項) を含む小さなMINLP
def baseline():
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3, name="n")
    s = m.addVar(lb=0.0, ub=10.0, name="s")
    m.addCons(n * s >= 12)                # 双線形のまま(McCormick緩和)
    m.setObjective(n + s, "minimize")
    return m

def improved():
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3, name="n")
    s = m.addVar(lb=0.0, ub=10.0, name="s")
    ns = mk.linearize_product(m, n, s, 1, 3, 0.0, 10.0, "ns")  # 厳密線形化
    m.addCons(ns >= 12)
    m.setObjective(n + s, "minimize")
    return m

# 1. 観測 + 診断
report = mk.analyze(baseline, name="baseline", time_limit=5)
print(report.summary())

# 2-3. 改善を適用し before/after を比較
df = mk.compare_variants({"baseline": baseline, "improved": improved}, time_limit=5)
print(df[["variant", "root_dual", "final_dual", "final_gap", "nodes"]].to_string(index=False))
```

## Documentation

- 📖 **ドキュメント**: <!-- 公開後に https://<OWNER>.github.io/<REPO>/ へ置換 -->
  `https://<OWNER>.github.io/<REPO>/`(GitHub Pagesで公開予定)
- 💻 **ローカル閲覧**: `uv run mkdocs serve` → http://127.0.0.1:8000
- 🧪 **試してみる(チュートリアルnotebook)**: [`notebooks/quickstart.ipynb`](notebooks/quickstart.ipynb) —
  小さなMINLPをその場で定義し、`analyze` → `linearize_product` → `compare_variants` を
  実行結果込みで確認できる
  <!-- 公開後に有効: Colabバッジ -->
  <!-- [![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/<OWNER>/<REPO>/blob/main/notebooks/quickstart.ipynb) -->
- 🖼️ **成果ギャラリー**: [`docs/gallery.md`](docs/gallery.md)(ダッシュボード・診断・比較結果のHTML集)

> 技術ノート: Colabでの試行はpyscipopt wheelにSCIPがネイティブ同梱されているため可能。
> JupyterLiteなどブラウザ内Python実行はSCIPネイティブバイナリを含められないため不可。

## Development

```powershell
uv sync                     # 開発依存(pytest/mkdocs/extras)込みでセットアップ
uv run pytest               # テスト(実SCIPで実行)
uv run mkdocs serve         # ドキュメントをローカルプレビュー
```
