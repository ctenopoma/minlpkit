# GPU warm start(cuOpt)

[← 利用マニュアル目次](index.md)

!!! info "このページの範囲"
    WSL2/Dockerでのcuopt導入手順とCLI/HTTPバックエンドの設定を扱う。効く原理・効かない条件・
    実測効果は[手法ガイド 7. GPU warm start](../playbook/07-gpu.md)を参照。

`mk.cuopt_warmstart` は「GPUは可行解探索、CPUは証明」という分業を1関数に閉じ込めたもの。
NVIDIA cuOpt(GPU上のMIPヒューリスティクス)を短時間走らせて可行解を掘り、SCIPへ
`addSol` で注入してから通常の `optimize()` に続ける。cuOpt自身は最適性証明をしないため、
下界の改善・最適性の証明はSCIP側に委ねる。手法の効果・効かない条件は
[手法ガイド 7. GPU warm start](../playbook/07-gpu.md) を参照。

## 導入(WSL2)

Windows上のSCIP/PySCIPOptはそのまま、cuOpt本体だけWSL2 Ubuntu上に別環境として置く
(cuOptはLinux + NVIDIA GPU前提のため)。

```bash
# WSL2 Ubuntu 内
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv --python 3.12 ~/cuopt-env
source ~/cuopt-env/bin/activate
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-cu13==25.10.*"
```

導入後、`~/cuopt-env/bin/cuopt_cli` がCLI実行ファイルになる。

## GPUが無い環境での挙動(設計)

- GPU機能は**完全に任意**。minlpkit本体の依存には何も追加されず(gpu.pyはstdlib+pyscipoptのみ)、
  cuOpt本体はWSL2側の別venvに置くため、**未導入環境でminlpkitが何かをダウンロードすることは無い**。
- 導入済みかは `mk.cuopt_available()` で確認できる(bool、プロセス内キャッシュ)。
  未導入のまま `cuopt_warmstart`/`cuopt_concurrent` を呼ぶと、導入手順つきの
  `RuntimeError` になる(素のsubprocessエラーは出さない)。
- 診断ルール `gpu_primal` の発火条件(GPU未導入でも発火する設計とその理由)は
  [手法ガイド 7. GPU warm start](../playbook/07-gpu.md)の「診断で何がわかるか」節を参照。
  recipeに本ページの導入手順への参照が含まれる。

## 使用例

```python
import minlpkit as mk

m = build_model()          # PySCIPOpt Model(最適化前)
res = mk.cuopt_warmstart(m, time_limit=15)
print(res["objective"], res["accepted"])  # cuOptが見つけた目的値 / SCIPへの注入可否

m.setParam("limits/time", 60)
m.optimize()                # 注入した解を起点にSCIPが証明を続ける
```

- `cuopt_cmd` で起動コマンドを差し替え可能。既定値はWSL2上の環境を想定している。
  (例: `["wsl", "-d", "Ubuntu", "--", "/home/username/cuopt-env/bin/cuopt_cli"]`)
  コマンドのリスト先頭が `"wsl"` で始まらなければネイティブ実行とみなし、Windows→WSLのパス変換をスキップする。
- cuOptが可行解を得られなかった場合(`.sol` が目的値ゼロ埋めのダミー)は注入をスキップし、
  `res["accepted"]` が `False` になる。
- 4アーム比較(純SCIP / cuOpt単体 / hybrid / concurrent)の worked example:
  `experiments/run_gpu_heuristic.py` → `results/gpu/<model>_<scale>_compare.csv`。

## 常駐型(並走): `mk.cuopt_concurrent`

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

## リモートサーバ構成(cuOpt self-hosted HTTP バックエンド)

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

> **実装の検証範囲**: 公式仕様への準拠 + モック契約テスト(`tests/test_gpu_http.py`、
> 公式のリクエスト/レスポンス形に忠実なモックサーバ)に加え、実サーバに対するE2E疎通
> (ヘルスチェック → 超小型MILP投入 → cuOpt目的値の取得 → SCIPへの `addSol` 注入)も
> 確認済み。無限境界は JSON が Infinity を表現できないため `±1e20` センチネルへ丸めており、
> 無限境界を含む問題での厳密さは環境によって検証が必要。

### GPUサーバ側のセットアップ

以下いずれかの方法で、GPUを持つホスト(Linux、またはWSL2を有効化したWindows)に
cuOptサーバを立てる。

**方法A: 公式Dockerコンテナ(推奨)**

```bash
# GPUホスト(Docker + NVIDIA Container Toolkit導入済み)で
# NGC にログイン(要 NVIDIA AI Enterprise / NGC APIキー)
docker login nvcr.io          # Username: $oauthtoken / Password: <NGC APIキー>

# cuOpt サーバコンテナを起動(GPU全公開、8000番でREST APIを待受)
docker run --gpus all -d --rm -p 8000:8000 -e CUOPT_SERVER_PORT=8000 \
  nvcr.io/nvidia/cuopt/cuopt:25.10
```

正確なイメージタグは [NGC カタログ](https://catalog.ngc.nvidia.com/)の「pull tag」で確認する
(バージョンにより `nvcr.io/nvidia/cuopt/cuopt:<tag>`。上は 25.10 系の想定)。
ホストのファイアウォールでポートを開放し、クライアントから到達可能にすること。

**方法B: pipパッケージから直接起動(WSL2等の既存Python環境がある場合)**

```bash
uv pip install --extra-index-url=https://pypi.nvidia.com "cuopt-server-cu13==25.10.*"
CUOPT_SERVER_PORT=8000 python -m cuopt_server.cuopt_service   # 提供される起動コマンドに従う
```

パッケージ名・起動コマンドはバージョンで異なりうるため、
[self-hosted server overview](https://docs.nvidia.com/cuopt/user-guide/25.10.00/cuopt-server/index.html)
で対象バージョンの正確な名称を確認する。WSL2からLANへポートを転送する場合は
`netsh interface portproxy` と該当ポートのファイアウォール開放が必要。

### クライアント側(このリポジトリ)

```python
import os, minlpkit as mk
os.environ["MINLPKIT_CUOPT_URL"] = "http://<gpu-host>:8000"   # これだけ
m = build_model()                       # 線形MILP、最適化前
res = mk.cuopt_warmstart(m, time_limit=15)
m.setParam("limits/time", 60); m.optimize()
```

サーバを立てたら、まず疎通確認スクリプトでE2E確認する(ヘルス + 超小型MILPの2段階):

```bash
uv run python experiments/check_cuopt_server.py --url http://<gpu-host>:8000
```

API: [`mk.cuopt_warmstart`/`mk.cuopt_concurrent`](../api/live.md)。
