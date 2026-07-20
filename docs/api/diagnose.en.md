# Diagnostic Rules (diagnose)

A diagnostic engine that passes the observation dict through threshold-based rules, returning the cause, recommendation, evidence, and fix instructions for each triggered symptom. It can be made pluggably extensible by appending `Rule`s to `mk.RULES` (list[Rule]).

::: minlpkit.collectors.diagnose
    options:
      members:
        - evaluate
        - Rule
        - RULES