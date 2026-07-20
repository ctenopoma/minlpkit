# 3. Big-M Elimination (tight M・Indicator)

[← Method Guide Index](index.en.md)

### Do you have these challenges?

- I am modeling fixed costs (facility opening, setup changes, etc.) with Big-M, but I have no criteria to decide what value M should be.
- The diagnosis outputs `numerical_scale` and says there are remaining Big-Ms in `residual_bigm_count`.

### What you can learn from the diagnostics

`numerical_scale` (warning) triggers on the residual coefficient ratio **after** presolve (`residual_coef_ratio ≥ 1e6`) or the number of remaining Big-Ms (`residual_bigm_count ≥ 1`). Note that it is designed not to make judgments based on the raw coefficient ratio before presolve (see "When it doesn't work" below).

### How the actions work

For a Big-M constraint $x \le M u$ ($u \in \{0,1\}$), the looser $M$ is (larger than the actually required value), the looser the LP relaxation becomes. This is because if $u$ is continuously relaxed between $0$ and $1$, $x \le M u$ hardly takes effect, as $x$ can move freely just by making $u$ a small fraction. There are 2 actions:

1. **tight M**: Narrow it down to the smallest $M = \overline{x}$ that can be derived from variable bounds, etc.
2. **Indicator constraints**: Pass logical constraints like $u = 1 \Rightarrow x \le c$ directly to SCIP's Indicator feature. It eliminates the need to pick a value for Big-M itself.

### Effect (Actual measurements in this repository)

In a fixed cost model (8 facilities) with loose Big-Ms, the pure LP relaxation bound improves from **1594 to 7127 (+347%)**, nearly reaching the optimal value of 7180 (FINDINGS §3, [`improve_bigm.html`](../gallery/improve_bigm.html)). The condition number also improves by **over 100 times**, from $\kappa(A) = 3.5\times10^{4}$ with loose Big-M to $\kappa(A) = 32$ with tightening (FINDINGS §3b).

![Before/after Big-M elimination: Pure LP relaxation bound, root dual bound with default settings, node count](../assets/playbook/03-bigm-effect.png)

To follow along with diagrams from the principle (how the size of M widens the LP relaxation region) to the effect measurement, see [Big-M Elimination (tight M・Indicator)](../notebooks/improve/03_bigm_indicator.en.ipynb).

### When it doesn't work / Notes

- **Note**: Despite the improvement in the LP relaxation bound mentioned above, **default SCIP automatically tightens loose Big-Ms during presolve**, so the final solving time often doesn't change much for small models (raw B&B node count showed only a small improvement of 11→9→8). You can tangibly feel the effect matching the numbers of the relaxation bound when you have large-scale/complex structures where presolve is less effective.
- The threshold for `numerical_scale` is judged based on the residual values **after** presolve (true ill-conditioning of 1e6). Do not judge it as "bad" just by looking at the coefficient ratio before presolve (e.g., 1e5) — in actual measurements, a typical case is 1e5 before presolve and 1.0 after presolve (Big-M candidates 8→0), which is designed not to trigger (FINDINGS §1).

### How to use

```python
# Indicator constraint (x <= c when u=1)
m.addConsIndicator(x <= c, binvar=u)
```

There is no dedicated helper like `mk.linearize_product`/`mk.pwl_sos2`; use PySCIPOpt's `addConsIndicator` directly. To check the condition numbers, use `matrix_condition(model)` (SVD, before solve) and `scip_basis_condition(model)` (SCIP LP basis, after solve). For details, see [8. Condition Number and Numerical Health](08-condition.en.md).
Worked example: `samples/others/fixed_charge.py`,
`experiments/run_improve_bigm.py` → [`improve_bigm.html`](../gallery/improve_bigm.html),
`experiments/run_condition.py` → [`condition.html`](../gallery/condition.html).
