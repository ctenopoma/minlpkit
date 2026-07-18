# チューニング (tune)

Optuna で問題クラスに特化した SCIP パラメータを探索する(SCIP が自動ではやらない
メタ最適化)。固定時間での双対境界を最大化する設定を求める。

追加依存(optuna)が必要。`uv add "minlpkit[tune]"` で導入する。

::: minlpkit.tune
    options:
      members:
        - tune
        - evaluate
        - default_dual
