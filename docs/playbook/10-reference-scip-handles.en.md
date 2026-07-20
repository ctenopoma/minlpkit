# Reference: What SCIP Handles Automatically

[← Method Guide Index](index.md)

The three methods on this page appear in textbooks but are **either processed automatically by modern SCIP by default**, or **are made worse by interfering**. We honestly show the conclusion that they are "normally unnecessary to handle" or "not recommended for regular use", along with actual measurements from this repository (FINDINGS.md). Implementation examples are left behind, but regular use is not recommended.

## Symmetry Breaking (Normally unnecessary to handle) {: #symmetry}

### Do you have these challenges?

- You feel the number of nodes is exploding because a massive amount of solutions with the same cost are generated.
- You have in mind symmetric structures like "all machines have the same performance" or "items are interchangeable".

### What the diagnosis reveals

`symmetry_info` (severity=**good**, meaning it is "information" and not a "recommendation") tells you the groups of interchangeable variables (detected by 1-hop color refinement, sound only for purely linear models).

### Mechanism of the solution (Why it's normally unnecessary)

The textbook countermeasure is "lexicographical ordering constraints" (forcing an order on symmetric variable groups to keep only one). However, SCIP automatically detects and handles symmetries via `misc/usesymmetry` (ON by default).

### Effect (measured in this repository)

In `makespan` (parallel machines) and `graph_coloring`, **all 4 combinations** of SCIP built-in symmetry ON/OFF × manual breaking ON/OFF **can be solved in 1 node** (FINDINGS §1). If manual lexicographical breaking is explicitly added, the number of nodes in makespan **worsens from 1 -> 24** (FINDINGS §2), because it cuts the LP feasible region asymmetrically and makes it harder.

### When it doesn't work / Cautions

- **Manual breaking is basically unnecessary, and can rather make things worse.** Lexicographical breaking is only effective under special operational conditions where `usesymmetry` is intentionally turned OFF (not normally done).
- Since symmetry detection itself can cause false positives when nonlinear constraints are present, the diagnosis is designed not to trigger for models with `sym_sound=False` (containing nonlinearities).

### How to use

See implementation examples only if the diagnosis triggers (regular use is not recommended):
`experiments/run_symmetry.py` -> [`symmetry.html`](../gallery/symmetry.html).

---

## Reduced Cost Fixing (SCIP default is sufficient) {: #redcost}

### Do you have these challenges?

- There are massive numbers of variables, and most are 0 in the optimal solution (columns seem "excessive").
- "The problem size doesn't shrink even in the later stages of the search".

### What the diagnosis reveals

There is no dedicated diagnose finding. Signs of excessive columns are judged from `decomposable` (block structure) or the model scale itself.

### Mechanism of the solution

A classical method where variables whose reduced cost r_j exceeds the "difference between the primal lower bound and current upper bound" can be fixed to 0 because they cannot enter the optimal solution.

### Effect (measured in this repository)

SCIP automatically performs this via `propagating/redcost` (ON by default). In `knapsack` (45 highly correlated items), default SCIP solves it in **0 nodes**. Comparing with bare branch-and-bound to isolate the effect: redcost ON 107 nodes / OFF 204 nodes (**-48%**), so the technique itself is effective, but SCIP already provides it (FINDINGS §1, [`improve_redcost.html`](../gallery/improve_redcost.html)).

### When it doesn't work / Cautions

- **Manual reimplementation is redundant.** It is treated not as "manual implementation required" but as "effective by SCIP default" even in diagnosis.
- If the columns become truly exponential and cannot even be enumerated, this becomes a matter of [6. Column Generation](06-column-generation.md) rather than reduced cost fixing.

### How to use

Reference implementation only: `experiments/run_improve_redcost.py` ->
[`improve_redcost.html`](../gallery/improve_redcost.html) (code to verify the technique's effectiveness via ON/OFF comparison). Nothing needs to be done in actual operation.

---

## Perspective Reformulation (Not recommended for regular use) {: #perspective}

### Do you have these challenges?

- You are considering "perspective formulation", which you saw in the literature, to tighten the relaxation of a model with on/off binaries × semi-continuous quadratic costs ($fc \ge au + bp + cp^2$, $p=0$ if $u=0$).

### What the diagnosis reveals

There is no dedicated finding. It is positioned as a theoretical option among general recommendations for `dual_stall`, but minlpkit does not actively recommend it for reasons below.

### Mechanism of the solution

Taking the perspective of just the quadratic term

$$
fc \ge au + bp + \frac{cp^2}{u}
\quad\Longleftrightarrow\quad
cp^2 \le (fc - au - bp)\,u
$$

is a reformulation that theoretically tightens the convex hull, and in the right-hand-side form, it can be written as a general nonlinear constraint.

### Effect (measured in this repository, negative result)

When applied to Unit Commitment (on/off × quadratic cost), **in default SCIP, the root dual bound went from 117067.24 -> 117067.71 (+0.0004%, practically unchanged)**. This is because presolve/separation automatically tightens the baseline convex quadratic. Comparing with bare branch-and-bound (presolve/separation/symmetry OFF), **it worsened from 113956 -> 57784 (-49% worse)** (FINDINGS §1・§2, [`perspective.html`](../gallery/perspective.html)).

### When it doesn't work / Cautions

- **Reason**: SCIP loosely relaxes the bilinear terms ($fc\,u$, $u^2$, $p\,u$) on the right side of the perspective constraint with McCormick, failing to capitalize on the true convex hull benefit of perspective (equivalent to rotated SOC). This is a failure pattern isomorphic to the negative effect of $n \cdot s \ge \text{demand}$ in [1. Exact Linearization](01-linearize.md) in the sense of "newly adding bilinear terms".
- Since it is an equivalent transformation, the optimal value itself remains unchanged (verified in a 4-period reduced scale, matching 32224.44 = 32224.44).
- **Conclusion: The bare convex quadratic lower bound is more advantageous for SCIP.** `mk.perspective_quadratic` is provided as a horizontally deployable component, but it should generally not be used.

### How to use (if you insist)

```python
import minlpkit as mk

mk.perspective_quadratic(m, u, p, fc, a=1.0, b=2.0, c=0.5, name="persp")
```

API: [`mk.perspective_quadratic`](../api/transforms.md) (Has a Warning in the docstring).
Worked example: `experiments/run_perspective.py` -> [`perspective.html`](../gallery/perspective.html).
