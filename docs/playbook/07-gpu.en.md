# 7. GPU warm start (cuOpt)

[← Method Guide Index](index.md)

!!! info "Scope of this page"
    Covers the principles of why GPU warm start works and its measured effects. For WSL2/Docker setup procedures and HTTP backend configuration, see [User Manual: GPU Setup](../manual/gpu-setup.md).

### Do you have these challenges?

- In large-scale MILPs with tens to hundreds of thousands of binary variables, feasible solutions cannot be found within the time limit, or even if found, they are few.
- You feel that "CPU branch-and-bound is strong for proving optimality, but slow for finding initial solutions".

### What the diagnosis reveals

`gpu_primal` (warning) triggers when "linear (no nonlinear) · 10,000+ binary variables · little variable overlap among equality constraints (`eq_overlap <= 1.5`) · few feasible solutions or slow TTFF · gap remains". It is designed to **trigger regardless of whether GPU/cuOpt is installed or not** (determined purely by problem structure. The philosophy is that "presenting the value of adoption" is the value of the diagnosis itself).

### Mechanism of the solution

cuOpt is a "primal heuristic engine on GPU + CPU-side B&B", where B&B and LP themselves are done on the CPU, but local searches like Feasibility Jump / Feasibility Pump are massively evaluated in parallel on the GPU. `mk.cuopt_warmstart` runs this for a short time, injects the found solutions into SCIP with `addSol`, and then passes them to the regular `optimize()`, dividing the labor so that "GPU searches for feasible solutions, CPU (SCIP) proves optimality". `mk.cuopt_concurrent` runs cuOpt in parallel in the background, and injects mid-solve via an event handler as soon as it finishes (reducing serial time spent waiting for GPU to zero).

### Effect (measured in this repository)

GAP large (75,000 binaries, tight capacity, 60 seconds): Pure SCIP gap **22.9%** (3 solutions) versus cuOpt standalone gap **0.64%**, hybrid (cuOpt injection -> SCIP) gap **4.72%** (FINDINGS §7. Artifacts are `results/gpu/gap_large_compare.html`, a local artifact generated only when run inside the repository, so not bundled in the documentation site). Even at xl scale (240,000 binaries, 120 seconds), the advantage holds: SCIP 20.72% / cuOpt 4.72% / hybrid 7.99%.

![GPU warm start before/after: Root dual bound, final gap, node count](../assets/playbook/07-gpu-effect.png)

To follow the process from the principle (how warm start changes the starting point of B&B pruning) to application and effect measurement with figures, see [GPU warm start](../notebooks/improve/07_gpu_warmstart.ipynb) (includes a fallback path for environments that cannot connect to a GPU server).

### When it doesn't work / Cautions

- **Does not work for structures where equality constraints share variables (set partitioning type)**. On set partitioning large (40,000 columns), cuOpt yields **zero feasible solutions** (both 60s/180s). The root LP degenerates and stagnates, never reaching the GPU heuristics. The discriminator is not the ratio of equalities but the **degree of variable overlap among equalities** (`eq_overlap`. Effective for GAP=1.0, misfires for set partitioning≈10, threshold 1.5). Consider [6. Column Generation](06-column-generation.md) for this structure.
- For small scales (2,000 variables), pure SCIP is better (60s: SCIP gap 0.43% vs cuOpt 1.37%). GPU is a technology effective for "large-scale MILPs where initial feasible solutions are hard to find" and has no role in small scales.
- With `cuopt_concurrent`, at scales where SCIP's root LP exhausts the time budget (xl class), events will not fire, resulting in zero injection opportunities. In such cases, use the serial `cuopt_warmstart` (the practical usage distinction is in FINDINGS §7).
- The GPU feature is completely optional and adds nothing to minlpkit's core dependencies. In uninstalled environments, `mk.cuopt_available()` returns False, and calling it raises a `RuntimeError` with installation instructions.

### How to use

```python
import minlpkit as mk

m = build_model()                          # Before optimization
res = mk.cuopt_warmstart(m, time_limit=15)  # Requires WSL2+cuOpt, or remote via server_url=...
m.setParam("limits/time", 60)
m.optimize()                                # SCIP continues the proof starting from injected solutions
```

API: [`mk.cuopt_warmstart` / `mk.cuopt_concurrent`](../api/live.md). Installation steps and remote server configuration are in [User Manual: GPU Setup](../manual/gpu-setup.md).
Worked example: `experiments/run_gpu_heuristic.py` -> `results/gpu/*_compare.html`
(local run artifacts), `experiments/gpu_dashboard.py` (comparison dashboard).
