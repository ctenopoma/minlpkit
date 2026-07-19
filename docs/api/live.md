# ライブ可視化 (live)

任意の `pyscipopt.Model` に使える問題非依存の求解モニタ(TensorBoard 型:書き手/読み手分離)。
書き手 `solve_with_monitor` / `RunLogger` が `<cwd>/results/runs/<run_id>/` にイベントを追記し、
読み手 `minlpkit.live.server`(Flask + SSE)がそれを tail してブラウザへライブ push する。
バッチ用途では `build_dashboard` で単一 HTML ダッシュボードも出せる。

追加依存(flask / plotly / kaleido)が必要。`uv add "minlpkit[viz]"` で導入する。

## モニタ

::: minlpkit.live.monitor
    options:
      members:
        - solve_with_monitor
        - SolveMonitor
        - primal_gap_series

## Run 条件キャプチャ

::: minlpkit.live.capture
    options:
      members:
        - capture_run_conditions

## Run ロガー

::: minlpkit.live.run_logger
    options:
      members:
        - RunLogger
        - new_run_id

## ダッシュボード

::: minlpkit.live.plots
    options:
      members:
        - build_dashboard

## ライブサーバ

::: minlpkit.live.server
    options:
      members:
        - main

## スイープ / rerun

::: minlpkit.live.sweep
    options:
      members:
        - sweep
        - rerun
