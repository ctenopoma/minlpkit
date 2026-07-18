"""SCIPパラメータの自動チューニング (Phase 4)

Optunaで問題クラスに特化したSCIPパラメータを探索する。SCIPが自動ではやらない
メタ最適化(モデラー/運用側が問題クラスに合わせて設定を特化させる)。

題材: 線形化版plant(難問だが改善余地あり)。固定時間での双対境界を最大化する
(双対境界が高い=gapが小さい)。探索対象は分離/ヒューリスティクス/presolve/分岐の
強度(SCIPのPARAMSETTINGレベル)と主要な数値パラメータ。

この機能は追加依存(optuna)を要する。extras 未導入で ``import minlpkit.tune``
すると、導入方法を案内する ImportError を送出する::

    uv add "minlpkit[tune]"
"""

from __future__ import annotations

try:
    import optuna
except ModuleNotFoundError as _e:  # pragma: no cover - extras 未導入時の案内
    raise ModuleNotFoundError(
        "minlpkit.tune には optuna が必要です。"
        '`uv add "minlpkit[tune]"` で導入してください。'
    ) from _e

from pyscipopt import SCIP_PARAMSETTING

_EMPHASIS = {"default": SCIP_PARAMSETTING.DEFAULT, "aggressive": SCIP_PARAMSETTING.AGGRESSIVE,
             "fast": SCIP_PARAMSETTING.FAST, "off": SCIP_PARAMSETTING.OFF}
_INF = 1e19


def _plant():
    """題材の scheduling_plant を遅延ロードする(リポジトリ運用時のデフォルト)。

    サンプルは配布パッケージには含めない。``import minlpkit.tune`` 自体は
    サンプルを要求せず、実際に `tune` を呼んだときだけ ``samples/`` を探す。
    """
    import sys
    from pathlib import Path

    samples = Path(__file__).resolve().parent.parent / "samples"
    if str(samples) not in sys.path:
        sys.path.insert(0, str(samples))
    import scheduling_plant as sp
    return sp


def _apply_params(m, params: dict) -> None:
    m.setSeparating(_EMPHASIS[params["separating"]])
    m.setHeuristics(_EMPHASIS[params["heuristics"]])
    m.setPresolve(_EMPHASIS[params["presolving"]] if params["presolving"] != "off"
                  else SCIP_PARAMSETTING.OFF)
    # 分岐規則の優先度を上げる
    m.setParam(f"branching/{params['branching']}/priority", 1000000)


def evaluate(params: dict, time_limit: float) -> float:
    """paramsで線形化plantを解き、固定時間での双対境界を返す。

    Args:
        params: separating / heuristics / presolving / branching の設定 dict。
        time_limit: 制限時間 [秒]。

    Returns:
        固定時間での双対境界(高いほど良い)。無限大なら 0.0。
    """
    sp = _plant()
    m = sp.build_model(linearize_ns=True)
    m.hideOutput()
    m.setParam("timing/clocktype", 2)
    m.setParam("limits/time", time_limit)
    try:
        _apply_params(m, params)
    except Exception:
        pass
    m.optimize()
    d = m.getDualbound()
    return d if abs(d) < _INF else 0.0


def default_dual(time_limit: float) -> float:
    """デフォルト設定で線形化plantを解いたときの固定時間双対境界を返す。

    Args:
        time_limit: 制限時間 [秒]。

    Returns:
        双対境界。無限大なら 0.0。
    """
    sp = _plant()
    m = sp.build_model(linearize_ns=True)
    m.hideOutput()
    m.setParam("timing/clocktype", 2)
    m.setParam("limits/time", time_limit)
    m.optimize()
    d = m.getDualbound()
    return d if abs(d) < _INF else 0.0


def tune(n_trials: int = 18, time_limit: float = 8.0) -> dict:
    """Optunaで双対境界を最大化するSCIPパラメータを探索する。

    線形化版plantを題材に、分離 / ヒューリスティクス / presolve / 分岐規則の
    強度をTPEで探索し、固定時間の双対境界を最大化する設定を求める。

    Args:
        n_trials: Optuna の試行回数。
        time_limit: 各試行の制限時間 [秒]。

    Returns:
        ``best_params`` / ``best_dual`` / ``default_dual`` / ``trials`` を持つ dict。
        ``trials`` は各試行の ``number`` / ``value`` / ``params`` のリスト。
    """
    def objective(trial: optuna.Trial) -> float:
        params = dict(
            separating=trial.suggest_categorical("separating", ["default", "aggressive", "fast", "off"]),
            heuristics=trial.suggest_categorical("heuristics", ["default", "aggressive", "fast", "off"]),
            presolving=trial.suggest_categorical("presolving", ["default", "aggressive", "fast"]),
            branching=trial.suggest_categorical("branching", ["relpscost", "pscost", "mostinf", "fullstrong"]),
        )
        return evaluate(params, time_limit)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(direction="maximize",
                                sampler=optuna.samplers.TPESampler(seed=1))
    base = default_dual(time_limit)
    study.enqueue_trial(dict(separating="default", heuristics="default",
                             presolving="default", branching="relpscost"))
    study.optimize(objective, n_trials=n_trials)
    return dict(
        best_params=study.best_params, best_dual=study.best_value, default_dual=base,
        trials=[dict(number=t.number, value=t.value, params=t.params)
                for t in study.trials if t.value is not None],
    )
