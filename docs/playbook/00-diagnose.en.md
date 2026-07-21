# 0. Diagnosis itself (analyze/findings/recipe)

[← Method Guide Index](index.en.md)

### Do you have these challenges?

- I wrote the model, but I don't understand why the gap isn't closing even after looking at the SCIP logs.
- I know some kind of improvement is necessary, but I can't determine where to start.
- Even if I attempt improvements, I can't objectively verify if they really worked, and it just ends up being a subjective impression.

### What you can learn from the diagnostics

`mk.analyze(build_fn, name, time_limit)` automatically collects the following behind the scenes during the solve and returns a `Report`:

- Dynamic: Attribution of the dual bound (which branching was effective), stagnation intervals, spatial branching ratio, number of nodes, number of feasible solutions, TTFF
- Nonlinear constraint violations ("which constraint is violated the most" in the relaxed solution)
- Static: Coefficient scale (before/after presolve), Big-M candidates, constraint-variable block structure (linking constraints)
- Symmetry (groups of swappable variables)

It mechanically applies 7 diagnostic rules (`minlpkit/collectors/diagnose.py`) to these observables (`report.metrics`) and returns the triggered symptoms in `report.findings`. Each finding has `symptom`, `cause` (suspected cause), `recommendation`, `evidence` (measured values), `recipe` (**mk function to use + worked example**), and `severity` (good/warning/serious/critical).
Since there is a `recipe`, "symptom → which page to read" is directly connected.

For the full table of diagnostic rules, refer to [User Manual: Workflow § Diagnostic rules list](../manual/workflow.en.md#rules).

### How the actions work

`analyze` itself is not an "action" but an "entry point that tells you which page to read next". The mechanism relies on simple threshold rules (e.g., "if relative violation of nonlinear constraints ≥ 0.5 and spatial branching ratio ≥ 0.3, then `weak_relaxation`"), not heavy judgments like Optuna or ML. All thresholds are determined from actual measurements in this repository (FINDINGS.md). The key point is that it judges based on the residual values **after** presolve, not **before** (e.g., `residual_coef_ratio`); this design prevents false positives for symptoms "that shouldn't be triggered because SCIP automatically tightens them" (see FINDINGS §1).

### Effect (Actual measurements in this repository)

Results of applying it in batch to about 50 models across 4 categories in `experiments/run_census.py` ([Diagnostic Benchmark](../census.en.md)):

- Out of 46 successful analyses, only 6 had a residual gap > 0.1%. Modern SCIP optimizes the vast majority instantly.
- The most frequently triggered were `symmetry_info` (23 models) and `decomposable` (9 models), which are **good (no action required)** informational findings. This is consistent with the conclusion that "textbook improvements are automatically handled by SCIP."
- The severe symptom `weak_relaxation` fired in only 1 out of 11 nonlinear models (`district_heating_detailed_physics`). Cases where the weakness of the non-convex relaxation is truly the bottleneck are rare, which is exactly why addressing it works when found (dive deeper with the [Violation Heatmap](../notebooks/diagnose/02_violation_heatmap.en.ipynb)).

### When it doesn't work / Notes

- Diagnosis is "detection of symptoms", not "automatic correction". Fully automated improvement is impossible in principle (you cannot mechanically detect "which products should be linearized" from an already built model). You must manually apply the mk functions suggested by the recipe.
- `dual_stall` and `wide_term_range` only tell you that "the symptom exists". Be sure to verify whether the fix is effective via before/after comparison with `mk.compare_variants` (see each page below).

### Look inside the diagnostic engine by trying it yourself

You can see exactly what each observable in `report.metrics` is calculating by checking the visualization notebooks, one deep-dive per collector.

- [1. McCormick Relaxation + Spatial Branch-and-Bound Tree](../notebooks/diagnose/01_mccormick_spatial_tree.en.ipynb) — Collection of `NODEBRANCHED` events underlying `spatial_share` and tree visualization
- [2. Violation Heatmap](../notebooks/diagnose/02_violation_heatmap.en.ipynb) — Measurement of violations in the root LP relaxation solution underlying `bottleneck_type`/`bottleneck_rel_viol`
- [3. Gap Stagnation and Attribution](../notebooks/diagnose/03_gap_stall_attribution.en.ipynb) — Detection of stagnation intervals for `n_stalls` and attribution of dual bound improvement to branching types
- [4. Static Diagnosis (Scale, Block Structure, Symmetry)](../notebooks/diagnose/04_static_diagnosis.en.ipynb) — Static observations before solve underlying `residual_coef_ratio`/`max_linking_groups`/`n_sym_groups`

### How to use

```python
import minlpkit as mk

report = mk.analyze(build_model, name="my_model", time_limit=20)
print(report.summary())
for f in report.findings:
    print(f["severity"], f["symptom"], "->", f["recipe"])
report.dashboard("results/report_my_model.html")
```

API: [`mk.analyze`](../api/pipeline.en.md) / [`mk.evaluate` and diagnostic rules](../api/diagnose.en.md).
Worked example: `demo.py`, `experiments/run_diagnose.py` → [`report_plant.html`](../gallery/report_plant.html) / [`diagnose_plant.html`](../gallery/diagnose_plant.html).