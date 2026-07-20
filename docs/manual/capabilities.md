# 機能マップ(できること一覧)

minlpkit で **何ができて・どの API で呼び・どのコマンドで試せて・何が出力されるか** を1枚に
対応づけた索引。全体は **観測 → 診断 → 改善 → 検証** の流れに沿う。各機能は問題非依存で、
任意の `pyscipopt.Model`(を返す `build_fn`)に適用できる。

各コマンドは `uv run python experiments/run_<name>.py`(コンソールで日本語が化ける場合は先に
`$env:PYTHONIOENCODING='utf-8'`)。出力 HTML は `results/` に書かれ、
`uv run python -m minlpkit.live.server` を起動すると
`http://127.0.0.1:5000/results/index.html`(成果ギャラリー)から一覧・閲覧できる。
単体 HTML なので `start results\<name>.html` で直接開いてもよい。

## 観測(可視化)

求解プロセスから症状のもとになる観測量を集めて可視化する。

| できること | API / 収集器 | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| 収束モニタ(primal/dual bound・gap・Primal Integral) | `mk.live.solve_with_monitor` | `run_monitor.py` | `results/<model>_dashboard.html` |
| 空間分枝木(分枝変数の型で色分け) | `collectors.tree` | `run_tree.py` | `results/tree.html` |
| 双対境界改善の分枝への帰属・gap停滞 | `collectors.attribution` | `run_attribution.py` | `results/attribution.html` |
| 非線形制約の違反量(ルート緩和のボトルネック) | `collectors.violation` | `run_violation.py` | `results/violation.html` |
| 非線形項の値域(区間演算で緩和の緩さを静的予測) | `collectors.interval` | `run_interval.py` | `results/interval.html` |
| 静的診断(係数スケール・Big-M・ブロック構造) | `collectors.static_diag` | `run_static_diag.py` | `results/static_<model>.html` |
| 対称性検出(入替可能な変数群) | `collectors.symmetry` | `run_symmetry.py` | `results/symmetry.html` |
| 行列条件数 κ(A)・LP基底条件数 | `collectors.static_diag` | `run_condition.py` | `results/condition.html` |
| McCormick 包絡の締まりアニメ | `viz.mccormick` | `run_mccormick.py` | `results/mccormick.html` |
| 実行可能モデルのボトルネック(スラック≈0×大きい影の価格) | `viz.bottleneck.analyze_slack` | `run_bottleneck.py` | `results/bottleneck.html` |

## 診断(SCIP-aware)

観測量を診断ルールに通し、SCIP が自動化しない改善だけを重要度順に推薦する。

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| 観測量収集 + 診断 → `Report`(症状→原因→推薦→根拠→直し方) | `mk.analyze(build_fn, ...)` | `run_diagnose.py` | `results/diagnose_<model>.html` |
| 診断ルールの適用(プラガブル) | `mk.RULES` / `mk.evaluate(metrics)` | — | — |
| 全サンプル一括診断(発火findingsの集計) | — | `run_census.py` | [診断ベンチマーク](../census.md) |
| **実行不可能(infeasible)の犯人特定** — 弾性緩和(緩める必要量)+ 削除フィルタ(IIS核)+ presolve当たり | `mk.diagnose_infeasibility` / `mk.elastic_filter` / `mk.deletion_filter` | `run_infeasibility.py` | `results/infeasibility.html` |

## 改善(再定式化・分解フレームワーク)

診断の推薦を実際に適用する。整数構造を突いた厳密線形化や、結合制約を境界にした分解。

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| 整数×連続の積を厳密線形化 | `mk.linearize_product` | `run_improve_linearize.py` | `results/improve_linearize.html` |
| 1変数関数を SOS2 で区分線形近似(Big-M不要) | `mk.pwl_sos2` | `run_sos.py` | `results/sos.html` |
| Big-M 排除(loose→tight/Indicator) | — | `run_improve_bigm.py` | `results/improve_bigm.html` |
| 半連続二次費用の遠近化(**常用非推奨**) | `mk.perspective_quadratic` | `run_perspective.py` | `results/perspective.html` |
| 列生成(Gilmore-Gomory / Wentges安定化) | `mk.column_generation` | `run_colgen.py` / `run_stabilize.py` | `results/colgen.html` / `stabilize.html` |
| branch-and-price(列生成 + 整数主問題) | `mk.price_and_branch` | `run_bnp.py` | `results/bnp.html` |
| ベンダーズ分解(コールバック方式) | `mk.benders` | `run_benders.py` | `results/benders.html` |
| 被約コスト固定(SCIP内蔵の伝播器) | — | `run_improve_redcost.py` | `results/improve_redcost.html` |

## 検証(before/after)

改善が本当に効いたかを定量比較する。

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| 定式化の before/after をルート双対境界・最終gap・ノード数で比較 | `mk.compare_variants({名前: build_fn})` | 各 `run_improve_*.py` | 各 `results/improve_*.html` |

## ライブ監視・run記録・再現(extras `viz`)

TensorBoard 型の**書き手/読み手分離**。求解が run ディレクトリへ追記し、サーバがブラウザへ
ライブ push する。詳細は [ライブ監視ガイド](../playbook/09-live-monitor.md) / [手順](live-monitor.md)。

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| 求解を計器化(境界トラジェクトリを run へ逐次追記) | `mk.live.solve_with_monitor(model, logger=RunLogger(...))` | `run_monitor.py` | `results/runs/<run_id>/` |
| ライブモニタ + 成果ギャラリーの配信 | `python -m minlpkit.live.server` | 同左 | `http://127.0.0.1:5000` |
| パラメータスイープ(parallel coordinates 比較) | `mk.sweep(build_fn, param_sets, ...)` | `run_sweep.py` | `results/sweep.html` |
| 記録した run 条件からの再現実行 | `mk.rerun(build_fn, run_id, ...)` | — | 新しい run |

## 自動チューニング(extras `tune`)

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| SCIPパラメータの Optuna 探索(問題クラス特化) | `mk.tune(n_trials, time_limit)` | `run_tune.py` | `results/tune.html` |

## GPU warm start(cuOpt × SCIP、要 WSL2/GPU)

| できること | API | 試すコマンド | 出力 |
| --- | --- | --- | --- |
| cuOpt(GPU)の解を SCIP へ warm start 注入 | `mk.cuopt_warmstart(model, ...)` | `run_gpu_heuristic.py` | `results/gpu/<model>_<scale>_compare.*` |
| cuOpt を SCIP と並走させ mid-solve 注入 | `mk.cuopt_concurrent(model, ...)` | 同左 | 同上 |
| 導入済みか確認 | `mk.cuopt_available()` | — | — |

導入手順は [GPU設定](gpu-setup.md) / [GPU warm start ガイド](../playbook/07-gpu.md)。

---

用途別に「症状から打ち手を選ぶ」なら [手法ガイド](../playbook/index.md)、API の詳細仕様は
[API リファレンス](../api/pipeline.md)、実際の出力例は [成果ギャラリー](../gallery.md) を参照。
