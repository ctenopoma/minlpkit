# 利用マニュアル

minlpkit の **観測(analyze)→ 診断(findings/recipe)→ 改善(transforms/frameworks)→ 検証(compare_variants)**
を1本で通すためのマニュアル。コード例はすべてコピペで動く(本リポジトリの doctest / demo で検証済み)。

## セットアップ

### リポジトリ内で使う

```powershell
uv sync
$env:PYTHONIOENCODING = 'utf-8'   # コンソールで日本語が化ける場合
uv run python demo.py
```

### 外部プロジェクトから使う

`minlpkit` は単体で成立する配布パッケージ(コアの実行時依存は pyscipopt/pandas/numpy/scipy のみ)。
ライブ可視化(`minlpkit.live`)とチューニング(`minlpkit.tune`)は追加依存を要する **extras**
(`viz` = flask/plotly/kaleido、`tune` = optuna)。コアだけなら extras は不要。

```powershell
# GitHub経由でインストール (最新版)
uv add git+https://github.com/ctenopoma/minlpkit.git                          # コアのみ(依存4つ)
uv add "minlpkit[viz,tune] @ git+https://github.com/ctenopoma/minlpkit.git"   # + ライブ可視化 / チューニング
```

```python
import minlpkit as mk   # これだけで analyze / compare_variants / transforms / frameworks が使える
# extras を入れると:
from minlpkit.live import solve_with_monitor, RunLogger   # 要 minlpkit[viz]
from minlpkit.tune import tune                            # 要 minlpkit[tune]
```

extras 未導入で `minlpkit.live` / `minlpkit.tune` を import すると、導入方法を案内する
ImportError(`uv add "minlpkit[viz]"` など)が出る。

---

## このマニュアルの範囲

このページはインストール手順とマニュアル全体の構成を示す。API仕様を網羅するリファレンスであり、
手法の選び方は [プレイブック(症状→打ち手)](../playbook/index.md) が扱う。プレイブックは
「gapが縮まらない」等の症状から該当する手法へ直接到達でき、「なぜ効くか」「どのくらい効くか」を
実測付きで説明する。各ページからは、原理・効果をグラフで確認できるnotebookにもリンクしている。

診断エンジンを全サンプルに一括適用した結果は [診断ベンチマーク](../census.md) にある。

## マニュアル構成

- **セットアップ**(このページ) — リポジトリ内 / 外部プロジェクトからの導入
- [ワークフロー全体像](workflow.md) — 観測→診断→改善→検証の流れ・一気通貫例・API/診断ルール表
- [制約・落とし穴](pitfalls.md) — 測定方法論・PySCIPOpt APIの注意点

ライブモニタの操作手順は [プレイブック 9. ライブ監視](../playbook/09-live-monitor.md) から、
GPU warm start の導入手順は [プレイブック 7. GPU warm start](../playbook/07-gpu.md) からそれぞれ
リンクしている。

API の詳細は [API リファレンス](../api/pipeline.md)(mkdocstrings 生成)を参照。
