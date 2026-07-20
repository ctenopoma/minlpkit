<div align="center">

<img src="docs/assets/icon.jpg" alt="minlpkit icon" width="120" />

# minlpkit

**PySCIPOpt(SCIP)で解くMINLPを、観測し・診断し・直し方を提案するツールキット。**

[![CI](https://github.com/ctenopoma/minlpkit/actions/workflows/docs.yml/badge.svg)](https://github.com/ctenopoma/minlpkit/actions/workflows/docs.yml)
[![Docs](https://img.shields.io/badge/docs-online-blue.svg)](https://ctenopoma.github.io/minlpkit/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Solver](https://img.shields.io/badge/solver-PySCIPOpt%20/%20SCIP-informational.svg)](https://github.com/scipopt/PySCIPOpt)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[ドキュメント](https://ctenopoma.github.io/minlpkit/) &nbsp;·&nbsp; [チュートリアル (Colab)](https://colab.research.google.com/github/ctenopoma/minlpkit/blob/main/notebooks/quickstart.ipynb) &nbsp;·&nbsp; [ギャラリー](https://ctenopoma.github.io/minlpkit/gallery.html)

</div>

![minlpkit hero](docs/assets/hero.png)

混合整数非線形計画(MINLP)の求解を、**観測 → 診断 → 改善 → 検証**の一連の流れで支援します。
求解プロセスから症状を観測し、診断ルールで効く改善を推薦し、再定式化ヘルパーやアルゴリズムフレームワークで
手を入れ、before/after を定量比較する。ここまでを 1 つのライブラリで通します。
推薦するのは SCIP が自動ではやらない改善だけ ── 非凸緩和の弱さを突く定式化の作り込みに集中します。

## Features

- **観測と診断** — `analyze` が双対境界の停滞・空間分枝の偏り・制約違反・係数スケール・対称性を収集し、症状を重要度順に返す
- **再定式化ヘルパー** — `linearize_product`(整数×連続の積を厳密線形化)や `pwl_sos2`(Big-M 不要の区分線形近似)で非凸緩和を締める
- **アルゴリズムフレームワーク** — ベンダーズ分解・列生成・branch-and-price をモデル非依存のドライバとして提供
- **before/after 検証** — `compare_variants` がルート双対境界・最終 gap・ノード数を並べ、改善の効果を定量化する
- **ライブモニタと自動チューニング** — 求解中の境界をブラウザへライブ配信し、Optuna で SCIP パラメータを探索(extras `viz` / `tune`)

## Installation

```powershell
# GitHub経由で最新版をインストール
uv add git+https://github.com/ctenopoma/minlpkit.git                          # コアのみ
uv add "minlpkit[viz,tune] @ git+https://github.com/ctenopoma/minlpkit.git"   # + ライブ可視化 / Optuna チューニング
```

## Quickstart

```python
import minlpkit as mk
from pyscipopt import Model

def baseline():   # n·s >= 12 を双線形のまま(McCormick 緩和)
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3, name="n")
    s = m.addVar(lb=0.0, ub=10.0, name="s")
    m.addCons(n * s >= 12); m.setObjective(n + s, "minimize")
    return m

def improved():   # 整数×連続の積を厳密線形化
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3, name="n")
    s = m.addVar(lb=0.0, ub=10.0, name="s")
    ns = mk.linearize_product(m, n, s, 1, 3, 0.0, 10.0, "ns")
    m.addCons(ns >= 12); m.setObjective(n + s, "minimize")
    return m

print(mk.analyze(baseline, name="baseline", time_limit=5).summary())
df = mk.compare_variants({"baseline": baseline, "improved": improved}, time_limit=5)
print(df[["variant", "root_dual", "final_dual", "final_gap", "nodes"]].to_string(index=False))
```

`analyze` は観測量と発火した診断を要約し、`compare_variants` は 2 つの定式化のルート境界・最終 gap・ノード数を
表で並べます。厳密線形化は最適値を変えずに緩和を締める変換で、規模のある問題ではルート双対境界と探索コストの差として
現れます。

## Documentation

ドキュメントは <https://ctenopoma.github.io/minlpkit/> にあります。
列生成・ベンダーズ・再定式化などの手法を知らない場合は
[プレイブック(症状→打ち手)](https://ctenopoma.github.io/minlpkit/playbook.html)から読むのが近道です。
[利用マニュアル](https://ctenopoma.github.io/minlpkit/manual.html)と
[API リファレンス](https://ctenopoma.github.io/minlpkit/api/pipeline.html)を参照してください。
[チュートリアル](https://ctenopoma.github.io/minlpkit/notebooks/quickstart.html)は
[Colab で直接実行](https://colab.research.google.com/github/ctenopoma/minlpkit/blob/main/notebooks/quickstart.ipynb)できます。
実際の求解結果は[ギャラリー](https://ctenopoma.github.io/minlpkit/gallery.html)にまとめています。
同梱する 126 本のサンプルは[サンプルカタログ](https://ctenopoma.github.io/minlpkit/samples/index.html)で
カテゴリ別に一覧できます(`uv run python experiments/gen_sample_catalog.py` で `docs/samples/` を再生成)。

## Development

```powershell
uv sync                     # 開発依存(pytest / mkdocs / extras)込みでセットアップ
uv run pytest               # テスト(実 SCIP で実行)
uv run mkdocs serve         # ドキュメントをローカルプレビュー
```
