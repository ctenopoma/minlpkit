# Campaigns and OpsOps (OpenTelemetry / Grafana)

minlpkit automates three recurring optimization chores with a single abstraction, the
**campaign** (a family of runs that vary along exactly one axis):

| Task | Axis | API |
| --- | --- | --- |
| Solve a batch of input scenarios (files) | input instance | `mk.scenario_sweep` |
| Tune SCIP parameters | parameters | `mk.sweep` |
| Find the culprit when solving stalls / is infeasible (toggle constraints on/off) | constraint group | `mk.ablate` |

Each member is recorded as a normal run under `results/runs/`, and the campaign summary
plus **verdicts (the library's suggestions)** are written to
`results/campaigns/<id>/campaign.json`.

## Constraint ablation (culprit hunting)

```python
import minlpkit as mk

# groups: {group name: constraint-name prefix or predicate}; omit to auto-group by prefix
df = mk.ablate(build_model, {
    "demand": "demand_",
    "kinetics": lambda name: name.startswith(("arrhenius_", "conversion_")),
}, name="plant", time_limit=15)
print(df[["axis", "status", "final_gap", "verdict"]])
```

The baseline (all constraints on) is compared against each group-off run:

- baseline infeasible → groups whose removal makes it solvable are flagged
  **involved in infeasibility** (critical); pin down the exact core with
  `mk.diagnose_infeasibility`
- baseline gap remains → groups whose removal (almost) closes the gap are flagged
  **convergence bottleneck** (serious)
- groups whose removal cuts solve time to 1/3 are flagged **dominant time factor** (warning)

## Scenario sweep

```python
df = mk.scenario_sweep(lambda sc: build_model(demand_scale=sc),
                       {"low": 0.6, "base": 1.0, "peak": 2.0}, name="plant")
```

Infeasible scenarios (critical) and hard instances that keep a large gap within the time
limit (warning) get verdicts.

## Viewing locally

```bash
uv run python -m minlpkit.live.server
```

http://127.0.0.1:5000/campaigns shows the cross-run matrix plus the suggestion panel;
each row links to the per-run live monitor.

## OpsOps: OpenTelemetry / Grafana

For continuous operation (daily scenario batches, performance-regression watching), ship
runs / campaigns via OTLP to **Grafana Alloy → Tempo / Loki / Prometheus → Grafana**:

```bash
uv add "minlpkit[otel]"
docker compose -f ops/docker-compose.yml up -d   # see ops/ in the repository
uv run python experiments/run_campaign.py --kind ablate --otel http://localhost:4318
# → http://localhost:3000 (Grafana) → Dashboards → minlpkit OpsOps
```

Signal mapping:

- **Traces (Tempo)**: campaign = parent span, each run = child span, incumbent updates =
  span events
- **Metrics (Prometheus)**: `opt_gap` / `opt_primal` / `opt_dual` / `opt_nodes`,
  backfilled with the real event timestamps
- **Logs (Loki)**: run summaries and verdicts (suggestions) with severity, correlated to
  Tempo via trace_id

Use `minlpkit.otel.export_run` / `export_campaign` to ship recorded runs after the fact.

!!! note "Metrics are complete only when shipped right after solving"
    Alloy's metrics conversion (`otelcol.exporter.prometheus`) silently drops data points
    older than a few minutes, so **backfilling old runs only delivers traces / logs**.
    Pass `--otel` when running the campaign so telemetry ships immediately. Minute-scale
    delays are absorbed by Prometheus' `storage.tsdb.out_of_order_time_window` (set in
    `ops/`). Logs older than 3 hours stay invisible until Loki flushes chunks
    (`POST /flush` forces it).
