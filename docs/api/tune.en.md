# Tuning (tune)

Searches for SCIP parameters specialized for a problem class using Optuna (meta-optimization not automatically handled by SCIP). Finds settings that maximize the dual bound within a fixed time.

Requires additional dependencies (optuna). Install with `uv add "minlpkit[tune]"`.

::: minlpkit.tune
    options:
      members:
        - tune
        - evaluate
        - default_dual