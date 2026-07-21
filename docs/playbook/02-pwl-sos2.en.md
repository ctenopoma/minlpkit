# 2. PWL Approximation (SOS2)

[← Method Guide Index](index.en.md)

### Do you have these challenges?

- I want to piecewise-linear approximate a non-convex 1-variable function (efficiency curve, power cost, etc.), but representing it with Big-M increases binary variables and makes it heavy.

### What you can learn from the diagnostics

It will be suggested as a piecewise linear approximation option in the recipe of `numerical_scale` (Big-M candidates remain after presolve) or `weak_relaxation` (nonlinear 1-variable term is the bottleneck).

### How the actions work

A piecewise linear function $y=f(x)$ can be represented by the convex combination of break points $(b_k, v_k)$.

$$
x = \sum_k b_k \lambda_k,\quad
y = \sum_k v_k \lambda_k,\quad
\sum_k \lambda_k = 1,\quad \lambda_k \ge 0 .
$$

Normally, Big-M + binaries are used to guarantee this "adjacency" (non-zero weights $\lambda_k$ are restricted to 2 consecutive points). However, if you pass an **SOS2 constraint** (Special Ordered Set type 2: at most 2 non-zeros, and they must be adjacent) directly to SCIP, you can express the exact same property without using any binary variables or Big-M. Since SCIP has a dedicated branching rule for SOS2 constraints, the search is lighter because it avoids extra auxiliary variables.

### Effect (Actual measurements in this repository)

In the PWL approximation of a non-convex 1-variable function, the Big-M version required **20 binary variables**, whereas the SOS2 version reaches the same optimal value with **0 binary variables** (FINDINGS §3, [`sos.html`](../gallery/sos.html)). The more break points you add, the closer the approximation gets to the true curve, but while Big-M binaries increase proportionally to the number of break points, SOS2 binaries remain at 0.

![Piecewise linear approximation of a non-convex function f(x) (varying the number of break points)](../assets/playbook/02-pwl-sos2-principle.png)

To follow along with diagrams on the trade-offs between break points, approximation error, and model scale, see [PWL Approximation (SOS2)](../notebooks/improve/02_pwl_sos2.en.ipynb).

### When it doesn't work / Notes

- Dedicated for 1-variable functions. It cannot be used for multivariable non-convex terms (like products) → in that case, consider [1. Strict Linearization of Integer × Continuous](01-linearize.en.md) or convex hull reformulation.
- As the number of segments increases, the approximation accuracy improves, but the number of $\lambda$ variables also increases (trade-off).

### How to use

```python
import minlpkit as mk

# Piecewise linear approximation of f(x)=x^2 with 3 points
y = mk.pwl_sos2(m, x, breakpoints=[0.0, 1.0, 2.0], values=[0.0, 1.0, 4.0], name="sq")
```

API: [`mk.pwl_sos2`](../api/transforms.en.md).
Worked example: `samples/physics_and_control_minlp/pwl_sos.py`,
`experiments/run_sos.py` → [`sos.html`](../gallery/sos.html).
