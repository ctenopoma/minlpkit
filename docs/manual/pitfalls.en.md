# Constraints and Known Pitfalls (User Perspective)

[← User Manual Index](index.en.md)

Key points from `FINDINGS.md`. Be aware that "modern SCIP automatically handles many textbook improvements."

## What SCIP Does Automatically (Do Not Recommend Manually)

"Modern SCIP automatically handles many textbook improvements." For details on the diagnostic logic, measured effects, and when to use the three techniques—Symmetry Breaking, Reduced Cost Fixing, and Perspective Reformulation—refer to [Method Guide Reference: What SCIP Does Automatically](../playbook/10-reference-scip-handles.en.md).

Key point only: **Loose Big-M's** are automatically tightened by presolve (manual handling is unnecessary in typical cases). The diagnosis determines this by the residual (`residual_scale`) **after** presolve, and the ratio threshold is set to 1e6 for true ill-conditioning (a natural cost difference of ~1e3 is not a numerical issue).

## "Improvements" that actually worsen things

- Naively adding the valid inequality $n \cdot s \ge \text{demand}$ actually adds a **new non-convex constraint** because $n \cdot s$ itself is bilinear, thus loosening the relaxation.
- **perspective_quadratic**: In theory, it tightens the convex hull, but since SCIP uses McCormick relaxation for the bilinear term on the right-hand side, it actually degrades the raw branch-and-bound by −49%. In default SCIP, the raw convex quadratic lower bound is more advantageous. **Provided as a component but not recommended for regular use.**

## Measurement Methodology (Avoiding Confounding)

- **Comparison by time limit is confounded by search dynamics** (adding constraints changes nodes/second). The quality of the formulation is evaluated by the **root dual bound** (`root_dual` in `compare_variants`) which has no confounding.
- To isolate the effect of a specific formulation, you should turn off compensatory mechanisms (presolve/separating/symmetry/propagation) explicitly and compare the raw branch-and-bound. Since modern SCIP solves small MILPs mostly in 1 root node, if you want to see the effect, you must create a subject of a scale/structure where the effect appears (like fixed_charge 8 facilities or graph_coloring in this repository).

## price_and_branch provides only an Upper Bound

- Because `price_and_branch` "solves the restricted master problem on the generated columns as integers", the integer solution returned is an **upper bound** ($z_{\mathrm{PB}} \ge z^\star$) of the true integer optimum, and is not a guarantee of optimality. Strict integer optimization requires full branch-and-price, where pricing is called at branching nodes. Optimality is proven if `lp_lb == int_obj` holds.

## PySCIPOpt API Pitfalls

- The key for `getValsLinear(cons)` is the **variable name string**. `Variable` does not have `getName()` (use `.name`).
- Branching information is obtained with `NODEBRANCHED` (`getParentBranchings()` is empty in `NODEFOCUSED`).
- `getSlack` does not support nonlinear constraints → for violations use `getNlRowSolFeasibility(nlrow, sol)` (negative = violation amount).
- Temporary `Model` objects in `build_fn()` should be kept in local variables (if GC'd during iteration, PySCIPOpt segfaults).
- The Windows SCIP clock has 1-second granularity → monitors should record using Python's `perf_counter`.