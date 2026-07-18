# 診断ルール (diagnose)

観測量 dict を閾値ベースのルールに通し、発火した症状ごとに原因・推薦・根拠・直し方を返す
診断エンジン。`mk.RULES`(list[Rule])に `Rule` を追加すればプラガブルに拡張できる。

::: minlpkit.collectors.diagnose
    options:
      members:
        - evaluate
        - Rule
        - RULES
