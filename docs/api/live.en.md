# Live Visualization (live)

A problem-independent solving monitor usable for any `pyscipopt.Model` (TensorBoard style: separation of writer/reader).
The writer `solve_with_monitor` / `RunLogger` appends events to `<cwd>/results/runs/<run_id>/`, and the reader `minlpkit.live.server` (Flask + SSE) tails it and live-pushes to the browser.
For batch use, a single HTML dashboard can also be output with `build_dashboard`.

Requires additional dependencies (flask / plotly / kaleido). Install with `uv add "minlpkit[viz]"`.

## Monitor

::: minlpkit.live.monitor
    options:
      members:
        - solve_with_monitor
        - SolveMonitor
        - primal_gap_series

## Run Condition Capture

::: minlpkit.live.capture
    options:
      members:
        - capture_run_conditions

## Run Logger

::: minlpkit.live.run_logger
    options:
      members:
        - RunLogger
        - new_run_id

## Dashboard

::: minlpkit.live.plots
    options:
      members:
        - build_dashboard

## Live Server

::: minlpkit.live.server
    options:
      members:
        - main

## Sweep / Rerun

::: minlpkit.live.sweep
    options:
      members:
        - sweep
        - rerun