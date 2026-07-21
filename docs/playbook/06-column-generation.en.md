# 6. Column Generation (Basics, Dual Stabilization, price-and-branch)

[← Method Guide Index](index.md)

### Do you have these challenges?

- The "possible patterns" (cutting patterns, shift patterns, routes, etc.) are exponentially large, and a compact formulation **cannot even be written down**.
- The term "column generation" is known, but specific implementation methods are often not shown.

### What the diagnosis reveals

There is no dedicated diagnose finding (sometimes `mk.column_generation` / `mk.price_and_branch` are suggested as choices in the recipe for `decomposable`). The situations where column generation is needed are for problems on a scale where "the model cannot even enumerate", which is akin to a design judgment prior to applying `analyze`.

## Basics (Gilmore-Gomory)

Restricted Master Problem (an LP using only the columns $p \in P'$ we currently have)

$$
\min \sum_{p \in P'} \lambda_p
\quad \text{s.t.} \quad
\sum_{p \in P'} a_p \lambda_p \ge d,\quad \lambda \ge 0
$$

is solved to obtain the dual $\pi$, and under that $\pi$, a column where the "reduced cost is negative (valuable)"—i.e., $1 - \pi^\top a_p < 0$—is generated just one at a time from a **pricing problem** (usually a small optimization like knapsack) and added to the master problem. This process is repeated. The key point is **to generate only the necessary columns on the fly, without listing them all** (intuitively, "instead of infinite choices, querying one by one only in the direction where we are losing").

```mermaid
flowchart LR
  RMP["Restricted Master Problem (RMP)<br>$$\min \sum_p \lambda_p$$<br>$$\text{s.t.} \sum_p a_p \lambda_p \ge d$$"] -->|"Dual $$\pi$$"| PRICE["Pricing Problem<br>$$\max \sum_i \pi_i a_i$$<br>s.t. pattern constraints"]
  PRICE -->|"Add a new column with<br>reduced cost $$1 - \pi^\top a \lt 0$$"| RMP
  PRICE -.->|"$$1 - \pi^\top a \ge 0$$<br>(no improving column)"| DONE([LP Optimal])

  style RMP fill:#eef6fc,stroke:#3b82f6,color:#1e3a8a
  style PRICE fill:#fff9e5,stroke:#f59e0b,color:#78350f
  style DONE fill:#f1fcf5,stroke:#10b981,color:#064e3b
```

`cutting_stock`: Generates **only 13 (9.9%)** of the 131 total patterns to reach the optimal LP bound of 23.55, and converges in 8 iterations (FINDINGS §3, [`colgen.html`](../gallery/colgen.html)). **Note**: This LP bound is **equivalent** to the material lower bound (23.52) of the compact formulation, and the value of column generation is not in "LP tightness" but in "implicitly handling exponential columns without enumerating them" (effective in practice on scales where compact formulation is impossible). The restricted master problem (integer) using only generated columns reaches the same integer optimal (24 rolls) in **just 1 node**, compared to a symmetric compact formulation (5231 nodes).

![Column generation convergence: RMP LP bound monotonically tightens to material lower bound](../assets/playbook/06-colgen-convergence.png)

To follow the process from the principle (RMP <-> pricing iteration) to effect measurement with figures, see [Column Generation](../notebooks/improve/06_column_generation.ipynb).

## Dual Stabilization (Wentges)

In degenerate problems, the dual $\pi$ oscillates heavily across iterations (tailing-off), slowing convergence.
Smoothing it towards a stabilization center $\pi_{\text{center}}$ (the dual of the best Farley lower bound) via

$$
\tilde\pi = \alpha\,\pi_{\text{center}} + (1-\alpha)\,\pi
$$

and passing it to pricing suppresses the oscillation. For a degenerate cutting stock problem (17 items), iterations went from **31 -> 25 (-19%)**, with the LP bound 382.75 unchanged (FINDINGS §3, [`stabilize.html`](../gallery/stabilize.html)). An overly large $\alpha$ (0.9) causes over-stabilization and fails to converge.

## price-and-branch

After column generation, the integer restricted master problem is solved using only the generated columns. **This is only an upper bound** (let the obtained value be $z_{\mathrm{PB}}$ and the true integer optimal be $z^\star$, we can only say $z_{\mathrm{PB}} \ge z^\star$; equality is not guaranteed). To guarantee strict integer optimality, branch-and-price requires pricing at each branch node, but if `lp_lb == int_obj` holds, optimality can be (consequently) proven. In cutting stock, an **integer optimal of 24 rolls** (matches ceil of LP lower bound = 24 = optimality proven) was found ([`bnp.html`](../gallery/bnp.html)).

### When it doesn't work / Cautions

- **`price_and_branch` has no optimality guarantee**. There is an example in a small test (W=10, widths [3,4,5], demands [3,3,3]) where `price_and_branch=5` against the true optimal=4 from enumerating all patterns in ILP (FINDINGS §4). Unless you confirm `lp_lb == int_obj`, do not definitively call it "optimal".
- PySCIPOpt's `getDualsolLinear` may fail due to constraints being NULLified in presolve. For obtaining duals in continuous LP, it is more reliable to use `res.ineqlin.marginals` from scipy's `linprog` (FINDINGS §4, internally implemented).

### How to use

```python
import minlpkit as mk

widths, rhs, W = [3, 4, 5], [3.0, 3.0, 3.0], 10
init = [[3, 0, 0], [0, 2, 0], [0, 0, 2]]

def pricing(duals):
    from pyscipopt import Model
    kp = Model(); kp.hideOutput()
    a = [kp.addVar(vtype="I", lb=0, name=f"a{i}") for i in range(3)]
    kp.addCons(sum(widths[i] * a[i] for i in range(3)) <= W)
    kp.setObjective(sum(duals[i] * a[i] for i in range(3)), "maximize")
    kp.optimize()
    return [round(kp.getVal(v)) for v in a], kp.getObjVal()

res = mk.column_generation(rhs, init, pricing, alpha=0.0)   # alpha>0 for Wentges stabilization
bnp = mk.price_and_branch(rhs, init, pricing)                # Integer solution (upper bound) + optimality check
```

API: [`mk.column_generation` / `mk.price_and_branch`](../api/frameworks.md).
Worked example: `experiments/run_colgen.py` / `run_stabilize.py` / `run_bnp.py` ->
[`colgen.html`](../gallery/colgen.html) / [`stabilize.html`](../gallery/stabilize.html) /
[`bnp.html`](../gallery/bnp.html).
