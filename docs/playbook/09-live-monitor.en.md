# 9. Live Monitor, Run Recording, and Rerun

[← Method Guide Index](index.md)

!!! info "Scope of this page"
    Covers why and when live monitoring and run recording are useful. For specific commands, RunLogger API, and detailed usage of sweep/rerun, see [User Manual: Live Monitor](../manual/live-monitor.md).

### Do you have these challenges?

- Waiting for a long solve without knowing "if it's stuck or progressing".
- Unable to recall previously tried settings later ("What were the parameters for that run?").
- Want to try several parameter combinations but lack a mechanism to compare them.

### What the diagnosis reveals

Live monitoring itself is independent of the diagnosis rules (a separate layer). However, the single run view has live simplified symptom banners (`detectLiveStall`/`detectNoIncumbent`/`detectHighGapDone`), which are a JS implementation of the same philosophy as `collectors/attribution.detect_stalls`. It is clearly stated as "Simplified live detection. Full diagnosis is performed by `mk.analyze`", not hiding that it is a subset of `mk.analyze`.

### Mechanism of the solution

TensorBoard-style "writer/reader separation". The writer (`solve_with_monitor`) appends solver events to files in `results/runs/<run_id>/`, and the reader (Flask+SSE server) tails them and live-pushes them to the browser. Just before solving, the SCIP parameter diffs, model fingerprint (variable/constraint breakdown), environment info, and git SHA are automatically captured and saved in `meta.json` (`capture=True` by default). This allows tracing "under what conditions a run was solved" later. For the overall architecture, see the diagram in [User Manual: Live Monitor](../manual/live-monitor.md).

`mk.sweep` is designed to brute-force a set of parameter candidates and **record each set as a regular run**, so the run comparison (checkbox selection) in the live UI serves exactly as a sweep result comparison without building a dedicated UI. `mk.rerun` reads the `scip_params_diff` of a recorded run and resolves under the same conditions (reproduction run).

### Effect (measured in this repository)

Confirmed live streaming of 338 SSE frames + done finalization in a 20-second solve. In actual data verification, the execution of `experiments/run_monitor.py --model plant --time 45` (826 events, gap 105.8%) correctly triggered the simplified live stall detection (windowRate 0.514 < 0.5×overallRate 1.712), and `detectHighGapDone` also triggered at gap 105.8% >= 50%.

### When it doesn't work / Cautions

- Live stall banners are "simplified detections" and do not output full diagnostic items (like `weak_relaxation`, etc.). For a proper diagnosis, run `mk.analyze` separately.
- `mk.rerun` cannot be used on runs without capture (old runs solved with `capture=False`) (`ValueError`). Do not opt out of capture for runs where you want to preserve reproducibility.

### How to use

```powershell
# Reader (keep open)
uv run python -m minlpkit.live.server   # http://127.0.0.1:5000

# Writer (different terminal)
uv run python experiments/run_monitor.py --model plant --time 120 --gap 0.01
```

```python
import minlpkit as mk

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(build_model, param_sets, name="sched", time_limit=10)
new_run_id = mk.rerun(build_model, df["run_id"][0], time_limit=20)
```

API: [`mk.sweep`/`mk.rerun`/`solve_with_monitor`/`RunLogger`](../api/live.md).
Details: [User Manual: Live Monitor](../manual/live-monitor.md).
