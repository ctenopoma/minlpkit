# 利用マニュアル — インストール

minlpkit の **観測(analyze)→ 診断(findings/recipe)→ 改善(transforms/frameworks)→ 検証(compare_variants)**
を1本で通すためのマニュアル。コード例はすべてコピペで動く(本リポジトリの doctest / demo で検証済み)。

> **列生成・ベンダーズ・再定式化などの手法を知らない場合**は、このマニュアル(API仕様の網羅)
> より先に [プレイブック(症状→打ち手)](../playbook/index.md) を読むほうが早い。症状から該当する
> 手法へ直接ジャンプでき、「なぜ効くか」「どのくらい効くか」を実測付きで説明している。
>
> 手を動かして学ぶなら、実サンプルで診断を読む
> [ハンズオン(1)可視化・診断編](../notebooks/hands_on_diagnosis.ipynb) と、recipe の効果を
> before/after で測る [ハンズオン(2)改善編](../notebooks/hands_on_improvement.ipynb) が近道。
> 診断エンジンを約50本のサンプルに一括適用した棚卸しは [診断センサス](../census.md) にある。

## マニュアル構成

- **インストール**(このページ) — リポジトリ内 / 外部プロジェクトからの導入
- [ワークフロー全体像](workflow.md) — 観測→診断→改善→検証の流れ・一気通貫例・API/診断ルール表
- [ライブモニタの使い方](live-monitor.md) — 書き手/読み手分離アーキテクチャ・run記録・rerun・スイープ
- [GPU warm start(cuOpt)](gpu-setup.md) — 導入・使用例・リモートサーバ構成
- [制約・落とし穴](pitfalls.md) — SCIPの自動処理・測定方法論・PySCIPOpt APIの注意点

API の詳細は [API リファレンス](../api/pipeline.md)(mkdocstrings 生成)を参照。

---

## リポジトリ内で使う

```powershell
uv sync
$env:PYTHONIOENCODING = 'utf-8'   # コンソールで日本語が化ける場合
uv run python demo.py
```

## 外部プロジェクトから使う

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
