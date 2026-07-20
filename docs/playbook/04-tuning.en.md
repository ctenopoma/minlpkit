# 4. SCIP Parameter Tuning (Optuna) and Sweep

[← Method Guide Index](index.en.md)

### Do you have these challenges?

- There are too many SCIP parameters (separating/heuristics/presolve/branching rules), and I can't determine which ones to adjust.
- I want to systematically find "settings that work for this set of models (multiple instances of the same problem class)".

### What you can learn from the diagnostics

Diagnostics are unrelated (parameter tuning is not a symptom-based recommendation subject, but a meta-optimization independent of model structure). However, the recipe for `dual_stall` suggests "verifying effectiveness with `mk.compare_variants`", and you should include the post-tuning settings in this verification loop.

### How the actions work

SCIP's behavior (separation strength, heuristic frequency, presolve aggressiveness, branching rules) can be controlled in bulk with `SCIP_PARAMSETTING` (default/aggressive/fast/off), etc. Since which combination maximizes the "dual bound at a fixed time" depends on the problem class and cannot be determined theoretically, it is explored using Bayesian optimization with Optuna (TPE sampler). `mk.sweep` is a simpler version of that, which compares candidate parameter sets by brute force.

### Effect (Actual measurements in this repository)

As a result of exploring settings to maximize the dual bound at a fixed 7 seconds for the linearized `plant` model, it improved from the default **134.8 to a best of 143.7 (+6.6%)**. The best setting is `separating=fast, heuristics=fast, branching=mostinf` (a configuration that lightens cuts/heuristics and pushes the dual with branching) (FINDINGS §3, [`tune.html`](../gallery/tune.html)).

![Before/after SCIP parameter tuning: Root dual bound, final gap, node count](../assets/playbook/04-tuning-effect.png)

To follow along with diagrams from the principle (differences in convergence curves due to parameters) to application and effect measurement, see [SCIP Parameter Tuning](../notebooks/improve/04_tuning.en.ipynb) (it also includes a real example showing that if Optuna explores with only the dual bound as the objective function, it might sacrifice feasible solutions).

### When it doesn't work / Notes

- The effect is an addition on the order of a few percent, which is small compared to the elaboration of formulations like [1. Strict Linearization](01-linearize.en.md) (+140%). The appropriate sequence is **first fix the formulation, and then parameters as the final finishing touch**.
- Since the search is specialized for a specific instance (or representative instances), it will not necessarily generalize to instances of a different scale or structure. In practice, it is practical to tune on a set of representative instances and fix those production settings.

### How to use

```python
from minlpkit.tune import tune   # extras: uv add "minlpkit[tune]"

result = tune(n_trials=18, time_limit=8.0)
print(result["default_dual"], result["best_dual"], result["best_params"])
```

Sweep (brute-force comparison; recorded as normal runs, so you can compare them directly in the Live UI):

```python
import minlpkit as mk

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(build_model, param_sets, name="sched", time_limit=10)  # Requires extras viz
```

API: `minlpkit.tune.tune` ([API Reference](../api/tune.en.md)), [`mk.sweep`/`mk.rerun`](../api/live.en.md).
Worked example: `experiments/run_tune.py` → [`tune.html`](../gallery/tune.html),
`experiments/run_sweep.py` → `results/sweep.html`.
