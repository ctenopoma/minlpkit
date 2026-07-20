# minlpkit 利用マニュアル

MINLP の **観測(analyze)→ 診断(findings/recipe)→ 改善(transforms/frameworks)→ 検証(compare_variants)**
を1本で通すためのマニュアル。コード例はすべてコピペで動く(本リポジトリの doctest / demo で検証済み)。

> 手を動かして学ぶなら、実サンプルで診断を読む
> [ハンズオン(1)可視化・診断編](notebooks/hands_on_diagnosis.ipynb) と、recipe の効果を
> before/after で測る [ハンズオン(2)改善編](notebooks/hands_on_improvement.ipynb) が近道。
> 診断エンジンを約50本のサンプルに一括適用した棚卸しは [診断センサス](census.md) にある。

---

## 1. インストール

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

## 2. ワークフロー全体像

```
観測  mk.analyze(build_fn)         → Report(metrics + findings)
  ↓
診断  report.findings / recipe     → 症状・原因・推薦・「具体的な直し方(使うmk関数+例)」
  ↓
改善  mk.linearize_product / pwl_sos2 / benders / column_generation を適用
  ↓
検証  mk.compare_variants({before, after})  → ルート双対境界・gap・ノードで before/after 比較
```

要点は **観測と改善を同じライブラリで閉じる**こと。診断の各 finding は `recipe`(使う mk 関数と
worked example)を持つので、「症状 → どの関数で直すか」が直結する。改善は本質的にモデル構造依存
なので全自動化はしない(SCIP ですら再定式化は自動化しない)。ライブラリが与えるのは
**再利用可能な部品 + 検証手順**である。

### 最小の一気通貫例(コピペ可)

```python
import minlpkit as mk
from pyscipopt import Model

# n·s >= 12 を、双線形のまま解く版と厳密線形化する版で比較
def baseline():
    m = Model(); m.hideOutput()
    n = m.addVar(vtype="I", lb=1, ub=3, name="n")
    s = m.addVar(lb=0.0, ub=10.0, name="s")
    m.addCons(n * s >= 12)                       # 双線形(McCormick緩和)
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

df = mk.compare_variants({"baseline": baseline, "improved": improved}, time_limit=5)
print(df[["variant", "root_dual", "final_dual", "final_gap", "nodes"]].to_string(index=False))
```

`demo.py` は同じ流れを実モデル(scheduling_plant)でやり、`analyze` の診断表示まで含む
フル版である。

---

## 3. API リファレンス

各 API の引数・返り値・注意点は **[API リファレンス](api/pipeline.md)** を参照してください。
ここでは各APIの役割と対応する worked example (実装例)を対応づけます。

| API | 役割 | worked example |
| --- | --- | --- |
| `mk.analyze(build_fn, name, time_limit, interval_terms_fn)` | 観測量収集 + 診断 → `Report` | `demo.py`, `experiments/run_diagnose.py` → `results/diagnose_*.html` |
| `mk.collect_metrics(build_fn, ...)` | 観測量 dict だけを集める(診断の入力) | `experiments/run_diagnose.py` |
| `mk.Report` | `metrics` / `findings` を保持。`.summary()` / `.dashboard(path)` | `results/report_plant.html` |
| `mk.compare_variants({名前: build_fn}, time_limit)` | before/after をルート双対境界・gap・ノードで比較 | `experiments/run_improve_linearize.py` → `results/improve_linearize.html` |
| `mk.linearize_product(m, y, x, y_lb, y_ub, x_lb, x_ub, name)` | 整数×連続の積を厳密線形化 | `samples/others/scheduling_plant.py`, `results/improve_linearize.html` |
| `mk.pwl_sos2(m, x, breakpoints, values, name)` | 1変数関数を SOS2 で区分線形近似(Big-M不要) | `samples/physics_and_control_minlp/pwl_sos.py`, `experiments/run_sos.py` → `results/sos.html` |
| `mk.perspective_quadratic(m, u, p, fc, a, b, c, name)` | 半連続二次費用の遠近化(**常用非推奨**、下記の落とし穴参照) | `experiments/run_perspective.py` → `results/perspective.html` |
| `mk.column_generation(rhs, init_columns, pricing_fn, alpha)` | 列生成(Gilmore-Gomory / Wentges安定化) | `experiments/run_colgen.py` / `run_stabilize.py` → `results/colgen.html` / `stabilize.html` |
| `mk.price_and_branch(rhs, init_columns, pricing_fn)` | 列生成 + 整数主問題(整数解は**上界**) | `experiments/run_bnp.py` → `results/bnp.html` |
| `mk.benders(master_build, subproblem_solve)` | ベンダーズ分解(コールバック方式) | `experiments/run_benders.py` → `results/benders.html` |
| `mk.cuopt_warmstart(model, time_limit, cuopt_cmd, server_url, mps_dir, heuristics_only)` | cuOpt(GPU)の解をSCIPへwarm start注入(WSL2 CLI or リモートHTTPサーバ) | `experiments/run_gpu_heuristic.py` → 下記「GPU warm start」 |
| `mk.cuopt_concurrent(model, time_limit, server_url, num_cpu_threads, ...)` | 常駐型: cuOptをSCIPと並走させ終了次第mid-solve注入(GPU待ちゼロ) | 下記「常駐型(並走)」 |
| `mk.RULES` / `mk.Rule` / `mk.evaluate(metrics)` | 診断ルール(プラガブル) | 下記「診断ルール一覧」 |

条件数など静的診断の補助関数として、
`matrix_condition(model)`(SVD による κ(A)、solve前)と `scip_basis_condition(model)`
(SCIP LP基底 κ、solve後)があります。worked example は `experiments/run_condition.py` → `results/condition.html`。

---

## 4. ライブモニタの使い方

TensorBoard 型(書き手/読み手分離)。2ターミナルで使う。

```powershell
# 読み手(開きっぱなし): ライブUI + 成果ギャラリー配信
uv run python -m minlpkit.live.server  # http://127.0.0.1:5000(後方互換: python -m viz.server も可)

# 書き手(別ターミナル): 求解しながら results/runs/<run_id>/ にログを追記
uv run python experiments/run_monitor.py --model plant --time 120 --gap 0.01
```

- ブラウザは最新 run を自動選択し、SSE で双対境界・primal gap・gap をライブ更新する。
- **run 比較モード**: run セレクタで2つの run を選ぶと、run A(青)/ run B(オレンジ)で双対・primal・gap
  を重ね描画する。凡例に run 名(モデル名 + 開始時刻 + status + 最終gap)が出る。
- **成果ギャラリー**: `http://127.0.0.1:5000/results/index.html` が `results/` の全成果物HTML
  (tree / attribution / violation / condition / benders / colgen / sos …)へのリンク集。

### run の記録と再現性

`solve_with_monitor(..., logger=...)` は求解直前に run 条件を自動キャプチャし、
`results/runs/<run_id>/meta.json` の `capture` キーへ残す(`capture=False` でオプトアウト)。
これにより「どの条件で解いた run か」が後から辿れる(最適化 MLOps の土台):

- **`scip_params_diff`**: 素の `Model()` のデフォルトと異なる SCIP パラメータの `{name: value}`。
  時間制限やヒューリスティクス設定など、その run 固有の設定だけが残る(既定 clocktype=2 のため
  通常は `limits/*` のみ、`setHeuristics(OFF)` 等で数十個)。
- **`fingerprint`**: presolve 前の変数内訳(`n_bin`/`n_int`/`n_cont`)・制約内訳(`n_linear`/
  `n_nonlinear`/`conss_by_handler`)・目的の向き・モデル名。
- **`env`**: minlpkit / Python / PySCIPOpt / SCIP のバージョンと OS。
- **`git_sha`**: 作業ディレクトリの git HEAD(リポジトリ内で git があるときのみ)。

各項目は独立に例外処理され、取得に失敗しても求解は止まらない(欠けた項目はキーごと省略)。
単体でも `minlpkit.live.capture_run_conditions(model)` として呼べる。既存 run(capture キーなし)は
そのまま server が読める(後方互換)。

### スイープ実行 + rerun

`minlpkit.live.sweep`(`mk.sweep` でも遅延importで利用可)は SCIP パラメータの候補群を総当たりする。
**各セットは通常の run として `results/runs/` に記録される**ため、上記のライブUI(runs一覧・
チェックボックス比較)がそのままスイープ結果比較UIになる(専用UIは無い)。

```python
import minlpkit as mk
import scheduling  # samples/

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(scheduling.build_model, param_sets, name="sched", time_limit=10)
# df: index / param_set / run_id / final_dual / final_gap / nodes / time / status
```

`mk.rerun(build_fn, run_id, time_limit=None)` は記録済み run の `meta.capture.scip_params_diff`
を読み出し、同じ `build_fn` の新モデルへ適用して再求解する(記録条件からの再現実行)。
新 run として記録され、`meta.rerun_of` に元の run_id が残る。capture の無い run(`capture=False`
で求解した旧run)には `ValueError` で明確に失敗する。

```python
new_run_id = mk.rerun(scheduling.build_model, df["run_id"][0], time_limit=20)
```

CLI: `uv run python experiments/run_sweep.py --model sched --time 6` で組み込みデモ
(separating/heuristics 強度を変える4セット)を実行し、`results/sweep.html` に
parallel coordinates 図(パラメータ軸 + final_dual/final_gap 軸)を出力する。
`--config sweep.yaml` で `param_sets:` を書いた任意の yaml を指定できる
(PyYAML は CLI 内でのみ使用、minlpkit のコア依存には追加していない)。

---

## 5. 診断ルール一覧(7ルール)

`minlpkit/collectors/diagnose.py` の `RULES` を転記。`mk.evaluate(metrics)` は発火したルールを
重要度順(critical→serious→warning→good)で返す。

| id | 症状 | 発火条件(閾値) | 推薦 / recipe |
| --- | --- | --- | --- |
| `weak_relaxation` (serious) | 特定の非線形制約に緩和違反が集中(かつ空間分枝が多い) | `bottleneck_rel_viol ≥ 0.5` かつ `spatial_share ≥ 0.3` | 区分線形近似・凸包再定式化・変数境界タイト化。**recipe**: 整数×連続は `mk.linearize_product`、非線形1変数は `mk.pwl_sos2`(例: improve_linearize.html, sos.html) |
| `wide_term_range` (warning) | 非線形項の値域(区間演算)が広い | `widest_term_rel ≥ 1.5` | 変数境界タイト化・区分線形化。**recipe**: `mk.linearize_product` か境界タイト化(例: interval.html, improve_linearize.html) |
| `dual_stall` (warning) | 双対境界の改善が停滞(gapが残る) | `n_stalls ≥ 1` かつ `gap ≥ 0.05` | 有効不等式追加・境界タイト化・Big-M排除で緩和強化。**recipe**: 効果は `mk.compare_variants` で検証(例: attribution.html) |
| `numerical_scale` (warning) | 係数レンジが桁違い / Big-M候補(presolve後も残存) | `residual_coef_ratio ≥ 1e6` または `residual_bigm_count ≥ 1` | スケーリング・Big-MのIndicator/SOS化。**recipe**: Big-Mを実bound/Indicator/SOSに置換、`mk.pwl_sos2`。条件数は `matrix_condition`/`scip_basis_condition` で確認(例: sos.html, condition.html) |
| `gpu_primal` (warning) | 大規模な線形バイナリ問題で可行解の発見が遅い/少ない(gapが残る) | `has_nonlinear=False` かつ `n_bin_vars ≥ 10000` かつ `eq_overlap ≤ 1.5` かつ(`nsols ≤ 3` または TTFFが求解時間の3割超)かつ `gap ≥ 0.05` | GPU primal heuristics のwarm start注入。**recipe**: `mk.cuopt_warmstart(m, time_limit=15)`(要 WSL2+cuOpt)。等式が変数を共有する集合分割型(`eq_overlap≫1`)はFJ系不発→列生成を検討(例: gap_large_compare.html) |
| `symmetry_info` (**good**) | 入替可能な変数群(対称性)を検出 | `sym_sound` かつ `largest_sym_group ≥ 3` | **通常は対応不要(SCIPが自動処理)**。usesymmetry を無効化した運用でのみ辞書式除去が有効(例: symmetry.html) |
| `decomposable` (good) | 制約-変数がブロック構造 + 少数の結合制約 | `max_linking_groups ≥ 4` かつ `n_heavy_linking ≤ 3` | ベンダーズ / Dantzig-Wolfe 分解。**recipe**: `mk.benders` か `mk.column_generation`/`mk.price_and_branch`(例: benders.html, bnp.html) |

`symmetry_info` が **good**(推薦でなく情報)なのは意図的。SCIP 内蔵の対称性処理が既定で対応し、
手動の辞書式除去は無効〜悪化するため(実測は落とし穴の節と `FINDINGS.md`)。

診断ルールはプラガブル。`mk.RULES.append(mk.Rule(...))` で独自ルールを足せる。

---

## 6. 制約・既知の落とし穴(利用者目線)

`FINDINGS.md` の要点。「教科書的改善の多くを現代の SCIP は自動でやる」ことに注意。

### SCIP が自動でやること(手動で推薦しない)

- **緩い Big-M**: presolve が自動でタイト化(係数比 1e5→1.0、Big-M候補 8→0)。手動 Big-M 対応は典型例では不要。
- **対称性**: `misc/usesymmetry`(既定ON)が自動対応。makespan / graph coloring は SCIP対称性 × 手動除去の
  全4通りが1ノードで解ける。**手動の辞書式除去はむしろ悪化**(LP を非対称に切って重くする)。
- **変数境界 / 被約コスト固定**: FBBT・`propagating/redcost`(既定ON)が自動実施。手動再実装は冗長。
- したがって診断は presolve **後**の残存(`residual_scale`)で判断し、比の閾値は真の悪条件 1e6
  (自然なコスト差 ~1e3 は数値問題ではない)にしてある。

### かえって悪化する「改善」

- 有効不等式 `n·s ≥ demand` を素朴に足すと、`n·s` 自体が双線形なので**新たな非凸制約の追加**になり緩和が緩む。
- **perspective_quadratic**: 理論上は凸包を締めるが、SCIP は右辺の双線形を McCormick 緩和するため
  素の分枝限定ではむしろ −49% 悪化。既定 SCIP では素の凸二次下界の方が有利。**部品として提供するが常用非推奨**。

### 測定方法論(交絡を避ける)

- **時間制限での比較は探索動学に交絡される**(制約追加でノード/秒が変わる)。定式化の質は
  **ルート双対境界**(`compare_variants` の `root_dual`)で測ると交絡がない。
- ある定式化の効果を分離するには、補償機構(presolve/separating/対称性/伝播)を明示的に OFF にして
  素の分枝限定で比べる。現代 SCIP は小規模 MILP を大抵ルート1ノードで解くので、効果を見たいなら
  効果が現れる規模/構造の題材を作る(本リポジトリの fixed_charge 8施設・graph_coloring 等)。

### price_and_branch は上界のみ

- `price_and_branch` は「生成列上の制限主問題を整数で解く」ため、返す整数解は真の整数最適の**上界**
  (≥ 真の最適)であって最適保証ではない。厳密な整数最適には pricing を分枝ノードで呼ぶ完全な
  branch-and-price が要る。`lp_lb == int_obj` が成り立てば最適性が証明される。

### PySCIPOpt の API 落とし穴

- `getValsLinear(cons)` のキーは**変数名の文字列**。`Variable` に `getName()` は無い(`.name` を使う)。
- 分枝情報は `NODEBRANCHED` で取る(`NODEFOCUSED` では `getParentBranchings()` が空)。
- `getSlack` は非線形制約に非対応 → 違反は `getNlRowSolFeasibility(nlrow, sol)`(負=違反量)。
- `build_fn()` の一時 Model はローカル変数に保持する(反復中に GC されると PySCIPOpt が segfault)。
- Windows の SCIP クロックは1秒粒度 → モニタは Python の `perf_counter` で記録する。

---

## 7. GPU warm start(cuOpt)

`mk.cuopt_warmstart` は「GPUは可行解探索、CPUは証明」という分業を1関数に閉じ込めたもの。
NVIDIA cuOpt(GPU上のMIPヒューリスティクス)を短時間走らせて可行解を掘り、SCIPへ
`addSol` で注入してから通常の `optimize()` に続ける。cuOpt自身は最適性証明をしないため、
下界の改善・最適性の証明はSCIP側に委ねる。

### 導入(WSL2)

Windows上のSCIP/PySCIPOptはそのまま、cuOpt本体だけWSL2 Ubuntu上に別環境として置く
(cuOptはLinux + NVIDIA GPU前提のため)。

```bash
# WSL2 Ubuntu 内
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 ~/cuopt-env
source ~/cuopt-env/bin/activate
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-cu13==25.10.*"
```

導入後、`~/cuopt-env/bin/cuopt_cli` がCLI実行ファイルになります。

### GPUが無い環境での挙動(設計)

- GPU機能は**完全に任意**。minlpkit本体の依存には何も追加されず(gpu.pyはstdlib+pyscipoptのみ)、
  cuOpt本体はWSL2側の別venvに置くため、**未導入環境でminlpkitが何かをダウンロードすることは無い**。
- 導入済みかは `mk.cuopt_available()` で確認できる(bool、プロセス内キャッシュ)。
  未導入のまま `cuopt_warmstart`/`cuopt_concurrent` を呼ぶと、導入手順つきの
  `RuntimeError` になる(素のsubprocessエラーは出さない)。
- **診断ルール `gpu_primal` はGPUの有無に関係なく発火する**(問題構造だけで判定)。
  これは意図した設計 — 「この問題クラスならGPU導入の価値がある」という提示自体が
  診断の価値のため。recipeに導入手順への参照が含まれる。

### 使用例

```python
import minlpkit as mk

m = build_model()          # PySCIPOpt Model(最適化前)
res = mk.cuopt_warmstart(m, time_limit=15)
print(res["objective"], res["accepted"])  # cuOptが見つけた目的値 / SCIPへの注入可否

m.setParam("limits/time", 60)
m.optimize()                # 注入した解を起点にSCIPが証明を続ける
```

- `cuopt_cmd` で起動コマンドを差し替え可能です。既定値はWSL2上の環境を想定しています。
  (例: `["wsl", "-d", "Ubuntu", "--", "/home/username/cuopt-env/bin/cuopt_cli"]`)
  コマンドのリスト先頭が `"wsl"` で始まらなければネイティブ実行とみなし、Windows→WSLのパス変換をスキップします。
- cuOptが可行解を得られなかった場合(`.sol` が目的値ゼロ埋めのダミー)は注入をスキップし、
  `res["accepted"]` が `False` になる。
- 4アーム比較(純SCIP / cuOpt単体 / hybrid / concurrent)の worked example:
  `experiments/run_gpu_heuristic.py` → `results/gpu/<model>_<scale>_compare.csv`。

### 常駐型(並走): `mk.cuopt_concurrent`

`cuopt_warmstart` がGPU完了を待つ直列型なのに対し、`cuopt_concurrent` はcuOptを
サブプロセスで走らせたまま即座に `optimize()` に入れる並走型。cuOptが終了し次第、
イベントハンドラが求解中のSCIPへ解を注入する(GPU待ちの直列時間ゼロ)。

```python
h = mk.cuopt_concurrent(m, time_limit=15, num_cpu_threads=8)
m.setParam("limits/time", 60)
m.optimize()               # cuOptと並走。終了し次第incumbentへ注入
info = h.result()          # injected / objective / inject_time / wall_time
```

- 実測(gap large): 直列hybrid=GPU 17s+SCIP 60s=計77s に対し、並走=計60sで同一解。
- 注入タイミングはSCIPのイベント発火間隔(ルートLP再解1回分の粒度)に律速される。
  **ルートLP自体が時間予算を食い尽くす規模(gap xl=24万バイナリ等)ではイベントが
  発火せず注入できない** — その場合は直列の `cuopt_warmstart` を使う(使い分けの実測は
  FINDINGS 7節)。`h.result()` の `n_events` が0ならこの状態。
- MPS/.sol はWSLネイティブ/tmpに自動ステージングされる(9p `/mnt/` のI/Oは
  このサイズで読み+20s/書き+19sと支配的に遅いため。FINDINGS 7節)。
- `num_cpu_threads` でcuOptのCPU側B&Bスレッドを絞り、並走中のSCIPとのCPU競合を抑える。

### リモートサーバ構成(cuOpt self-hosted HTTP バックエンド)

同一マシンのWSL2 CLIを叩く代わりに、**LAN上のGPUマシンで cuOpt サーバ(REST API)を
立てて HTTP で叩く**構成にも対応する。クライアント側は環境変数 `MINLPKIT_CUOPT_URL`
(または `server_url=` 引数)を設定するだけで、`mk.cuopt_warmstart` / `mk.cuopt_concurrent` /
`mk.cuopt_available` が自動的にHTTPバックエンドへ切り替わる(解決順: 引数 > 環境変数 > CLI)。

**API仕様(調査結果、出典つき)**: 公式クライアント `cuopt-sh-client` は MPS を
**クライアント側で** cuOpt データモデルJSONへパースし、`POST /cuopt/request` に JSON として送る
(生MPSを受け付けるHTTPエンドポイントは存在しない)。本バックエンドも同じデータモデルJSON
(`csr_constraint_matrix` / `constraint_bounds` / `objective_data` / `variable_bounds` /
`variable_types` / `variable_names` / `solver_config`)を PySCIPOpt の線形構造から直接組み立てて送る
(`cuopt_mps_parser` 依存を避けるため。**線形MILP専用** — cuOpt自体がMILP専用)。応答が
`{"reqId": ...}` のみなら `GET /cuopt/solution/{reqId}` をポーリングし、
`response.solver_response.solution.vars`(変数名→値)/ `primal_objective` / `status` を取り出して
SCIP互換 .sol 化 → `readSolFile` + `addSol` で注入する。ヘルスは `GET /cuopt/health`(200)。
（出典: [cuOpt self-hosted server (25.10)](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/quick-start.html)、
[client-api reference](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/client-api/sh-cli-api.html)、
[LP/MILP examples](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/examples/milp-examples.html)、
wire形式は [NVIDIA/cuopt](https://github.com/NVIDIA/cuopt) の `python/cuopt_self_hosted/cuopt_sh_client`）

> **重要(正直な注記)**: 実cuOptサーバはこの開発環境には無いため、**実サーバE2Eは未実施**。
> 実装は上記公式仕様への準拠 + モック契約テスト(`tests/test_gpu_http.py`、公式のリクエスト/
> レスポンス形に忠実なモックサーバ)まで。ユーザーがサーバを立てた後、
> `experiments/check_cuopt_server.py` で実E2E確認する。無限境界は JSON が Infinity を
> 表現できないため `±1e20` センチネルへ丸めており、実サーバでの無限表現の厳密さは未検証。

#### GPUサーバ側のセットアップ(2ルート。例: LAN上の Windows マシン `192.168.50.37`、WSL2あり)

**ルートA: Docker Desktop で公式 cuOpt サーバコンテナを起動(推奨・簡便)**

```powershell
# GPUマシン(Windows + Docker Desktop + WSL2 backend + NVIDIA Container Toolkit)で
# NGC にログイン(要 NVIDIA AI Enterprise / NGC APIキー)
docker login nvcr.io          # Username: $oauthtoken / Password: <NGC APIキー>

# cuOpt サーバコンテナを起動(GPU全公開、8000番でREST APIを待受)
docker run --gpus all -d --rm -p 8000:8000 -e CUOPT_SERVER_PORT=8000 `
  nvcr.io/nvidia/cuopt/cuopt:25.10

# Windows ファイアウォールで 8000/tcp を LAN に開放(管理者PowerShell)
New-NetFirewallRule -DisplayName "cuOpt 8000" -Direction Inbound `
  -Action Allow -Protocol TCP -LocalPort 8000
```
※ 正確なイメージタグは [NGC カタログ](https://catalog.ngc.nvidia.com/)の「pull tag」で確認
（バージョンにより `nvcr.io/nvidia/cuopt/cuopt:<tag>`。上は 25.10 系の想定)。

**ルートB: 既存の WSL2 cuopt-env に cuopt-server(pip)を入れて起動 + netsh で LAN 公開**

FINDINGS §7 のGPU実測はこの `192.168.50.37` の WSL2(cuopt-env)で行われていた。既存venvを流用する場合:

```bash
# GPUマシンの WSL2 Ubuntu 内(既存 ~/cuopt-env を流用)
source ~/cuopt-env/bin/activate
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-server-cu13==25.10.*"
# サーバ起動(0.0.0.0 で待受。ポートは環境変数で指定)
CUOPT_SERVER_PORT=8000 python -m cuopt_server.cuopt_service   # 提供される起動コマンドに従う
```
```powershell
# WSL2 の待受を Windows ホスト経由で LAN 公開(管理者PowerShell)。<WSL_IP> は `wsl hostname -I`
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=8000 `
  connectaddress=<WSL_IP> connectport=8000
New-NetFirewallRule -DisplayName "cuOpt 8000" -Direction Inbound `
  -Action Allow -Protocol TCP -LocalPort 8000
```
※ `cuopt-server` のパッケージ名/起動コマンドはバージョンで異なりうる。
[self-hosted server overview](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/index.html) で対象バージョンの正確な名称を確認すること。

#### クライアント側(このリポジトリ)

```python
import os, minlpkit as mk
os.environ["MINLPKIT_CUOPT_URL"] = "http://192.168.50.37:8000"   # これだけ
m = build_model()                       # 線形MILP、最適化前
res = mk.cuopt_warmstart(m, time_limit=15)
m.setParam("limits/time", 60); m.optimize()
```

サーバを立てたら、まず疎通確認スクリプトでE2E確認する(ヘルス + 超小型MILPの2段階):

```bash
uv run python experiments/check_cuopt_server.py --url http://192.168.50.37:8000
```
