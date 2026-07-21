# Results Gallery

A collection of HTML outputs demonstrating the execution of each `minlpkit` feature (visualization, diagnosis, and validation of improvements) on actual sample models.
All outputs from `experiments/run_*.py` and `demo.py` are embedded directly (plotly.js inline, static HTML including execution results). ★ denotes a "truly valuable improvement" not automatically handled by SCIP.

- 🖥️ **Results Index (Original Homepage)**: [gallery/index.html](gallery/index.html)

## Visualization

| Page | Content |
| --- | --- |
| [Convergence Monitor (plant)](gallery/plant_dashboard.html) | Primal/dual bound transition, gap log, Primal Integral |
| [Convergence Monitor (UC)](gallery/uc_dashboard.html) | Unit Commitment solving trajectory |
| [McCormick Convex Relaxation](gallery/mccormick.html) | 3D animation showing bilinear term relaxation tightened by interval partitioning |
| [Spatial Branch-and-Bound Tree](gallery/tree.html) | Colored by branching variable type (spatial/integer/0-1) |
| [Gap Stagnation and Effective Branching](gallery/attribution.html) | Attribution of dual bound improvement to branching |
| [Nonlinear Constraint Violations](gallery/violation.html) | Heatmap of bottleneck constraints in the root relaxation |
| [Slack/IIS](gallery/bottleneck.html) | Binding of linear constraints, IIS (deletion filter method) |
| [Static Diagnosis (plant)](gallery/static_plant.html) | Coefficient scales, block structures, linking constraints |
| [Static Diagnosis (UC)](gallery/static_uc.html) | Big-M detection, ill-conditioned constraints |
| [Interval Arithmetic Range](gallery/interval.html) | Static prediction of relaxation looseness from nonlinear term ranges |
| [Symmetry Detection](gallery/symmetry.html) | Interchangeable variable groups (color refinement) |

## Diagnosis (SCIP-aware)

| Page | Content |
| --- | --- |
| [minlpkit Report (plant)](gallery/report_plant.html) | `analyze()` integrated report: observations + recommendations |
| [Diagnosis (plant)](gallery/diagnose_plant.html) | Symptoms → Causes → Recommendations → Evidence |
| [Diagnosis (UC)](gallery/diagnose_uc.html) | Detection of residual Big-M |
| [Diagnosis (Parallel Machine)](gallery/diagnose_parallel.html) | Symmetry = SCIP automatic processing (info) |
| [Diagnosis (Facility Location)](gallery/diagnose_facility.html) | No symptoms (healthy) |

## Implementing Improvements and Validating Effects

| Page | Content |
| --- | --- |
| [n·s Exact Linearization ★](gallery/improve_linearize.html) | True improvement SCIP doesn't do: root bound +140% |
| [Column Generation (GG) ★](gallery/colgen.html) | Implicitly handles exponential columns (optimal LP in 13/131) |
| [Optuna Tuning](gallery/tune.html) | Problem class specialization with dual bound +6.6% |
| [Big-M Elimination](gallery/improve_bigm.html) | LP relaxation +347% (compensated by presolve) |
| [Reduced Cost Fixing](gallery/improve_redcost.html) | Provided by SCIP. -48% on bare B&B |
| [Benders Decomposition ★](gallery/benders.html) | Master/sub-decomposition converges to single-problem optimal value (3 iterations) |
| [Condition Number κ(A) Diagnosis](gallery/condition.html) | Core of Model Analyzer. Detects UC basis κ=2.6e11 |
| [Dual Stabilization of Column Generation ★](gallery/stabilize.html) | Wentges smoothing reduces iterations by 19% (suppresses tailing-off) |
| [SOS2 Piecewise Linear Approximation](gallery/sos.html) | Avoids Big-M. 0 binaries vs 20 for Big-M version |
| [Branch-and-Price ★](gallery/bnp.html) | Generic driver achieves integer optimum 24 rolls (optimality proof) |
| [Perspective Reformulation](gallery/perspective.html) | Negative result: invariant by default, -49% if bare (SCIP weakens with McCormick) |

---

★ = "Truly valuable improvement" not automatically handled by SCIP. Others are re-verifications of built-in SCIP features, or formulation differences compensated by presolve. If you want to run your own models on the live monitor, refer to `uv run python -m minlpkit.live.server` ([User Manual: Live Monitor](manual/live-monitor.md)).