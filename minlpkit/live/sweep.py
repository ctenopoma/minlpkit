"""SCIPパラメータのスイープ実行 + rerun (Phase 10 C3)

設計の要: スイープの各メンバーは**通常の run** として `results/runs/` に記録される
(capture付き)。これにより C2 の runs一覧UI(チェックボックス比較)がそのまま
スイープ結果の比較UIになる — スイープ専用の別UIを作らない。

`rerun` は記録済み run の `meta.capture.scip_params_diff`(非デフォルトのSCIP
パラメータ差分)を読み出し、同じ build_fn の新モデルに適用して再求解する
(「記録された条件からの再現実行」)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pandas as pd
from pyscipopt import Model

from .monitor import solve_with_monitor
from .run_logger import RUNS_ROOT, RunLogger, new_run_id

_INF = 1e19


def _unique_run_id(model_name: str, root: Path) -> str:
    """`new_run_id` の秒精度では高速な連続呼び出し(スイープ/rerun)が衝突しうるため、
    既存ディレクトリと重ならない run_id になるまで連番を足す。"""
    run_id = new_run_id(model_name)
    candidate = run_id
    suffix = 2
    while (Path(root) / candidate).exists():
        candidate = f"{run_id}_{suffix}"
        suffix += 1
    return candidate


def sweep(
    build_fn: Callable[[], Model],
    param_sets: list[dict],
    *,
    name: str = "sweep",
    time_limit: float = 20.0,
    runs_root: Path | None = None,
) -> pd.DataFrame:
    """SCIPパラメータの候補を総当たりし、各結果を run として記録する。

    各 ``param_set`` について ``build_fn()`` で新しいモデルを作り、``setParam`` で
    パラメータを適用してから `solve_with_monitor` で求解する。`solve_with_monitor`
    の既定 ``capture=True`` により各 run の ``meta.json`` に
    ``capture.scip_params_diff`` として適用したパラメータが自動記録されるため、
    後から `rerun` で同じ条件を再現できる。加えて ``meta.sweep`` に
    ``{"name", "index", "param_set"}`` を追記し、スイープ由来であることを残す。

    Args:
        build_fn: 引数なしで新しい ``Model`` を返す callable(呼ぶたびに新規モデル)。
        param_sets: SCIP パラメータの候補群。各要素は ``{パラメータ名: 値}`` の dict
            (例: ``{"separating/maxroundsroot": 0}``)。
        name: run_id の接頭辞・``meta.model`` に使う識別子。
        time_limit: 各セットの制限時間 [秒]。
        runs_root: run を書き出す先。``None`` なら既定の
            `minlpkit.live.run_logger.RUNS_ROOT`(``<cwd>/results/runs``)。

    Returns:
        pandas.DataFrame: 1セット1行。列は ``index`` / ``param_set``(str化) /
        ``run_id`` / ``final_dual`` / ``final_gap`` / ``nodes`` / ``time`` / ``status``。

    Example:
        ```python
        >>> import contextlib, io, tempfile
        >>> from pathlib import Path
        >>> from pyscipopt import Model, quicksum
        >>> from minlpkit.live import sweep
        >>> def build():
        ...     m = Model(); m.hideOutput()
        ...     x = {i: m.addVar(vtype="B", name=f"x{i}") for i in range(6)}
        ...     m.addCons(quicksum(x.values()) <= 3)
        ...     m.setObjective(quicksum((i + 1) * x[i] for i in x), "maximize")
        ...     return m
        >>> with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        ...     df = sweep(build, [{"limits/gap": 0.0}, {"limits/gap": 0.5}],
        ...                name="doctest_sweep", time_limit=5, runs_root=Path(tmp))
        >>> len(df)
        2
        >>> sorted(df.columns) == sorted(
        ...     ["index", "param_set", "run_id", "final_dual", "final_gap",
        ...      "nodes", "time", "status"])
        True

        ```
    """
    root = runs_root if runs_root is not None else RUNS_ROOT
    n = len(param_sets)
    rows = []
    for i, param_set in enumerate(param_sets):
        m = build_fn()
        m.hideOutput()
        m.setParam("timing/clocktype", 2)
        for k, v in param_set.items():
            m.setParam(k, v)

        run_id = _unique_run_id(name, root)
        logger = RunLogger(
            run_id,
            meta=dict(model=name, title=f"{name} #{i}",
                      params=dict(time_limit=time_limit, param_set=param_set)),
            root=root,
        )
        _, summary = solve_with_monitor(m, time_limit=time_limit, logger=logger)
        logger.update_meta({"sweep": {"name": name, "index": i, "param_set": param_set}})

        row = dict(
            index=i, param_set=str(param_set), run_id=run_id,
            final_dual=summary["dual"], final_gap=summary["gap"],
            nodes=summary["nodes"], time=summary["time"], status=summary["status"],
        )
        rows.append(row)
        gap_pct = f"{row['final_gap'] * 100:.2f}%" if row["final_gap"] is not None else "n/a"
        print(f"[{i + 1}/{n}] {run_id}  param_set={param_set}  "
              f"dual={row['final_dual']}  gap={gap_pct}  nodes={row['nodes']}")

    return pd.DataFrame(rows, columns=["index", "param_set", "run_id", "final_dual",
                                        "final_gap", "nodes", "time", "status"])


def rerun(
    build_fn: Callable[[], Model],
    run_id: str,
    *,
    runs_root: Path | None = None,
    time_limit: float | None = None,
) -> str:
    """記録済み run の条件(capture)から同じ求解を再現する。

    ``run_id`` の ``meta.json`` から ``capture.scip_params_diff``(非デフォルトの
    SCIP パラメータ差分。``solve_with_monitor(..., capture=True)`` が記録したもの)を
    読み出し、``build_fn()`` で作った新しいモデルに ``setParam`` で適用してから
    再求解する。新しい run として `results/runs/` に記録し、``meta.rerun_of`` に
    元の ``run_id`` を残す。

    Args:
        build_fn: 引数なしで新しい ``Model`` を返す callable。元の run と同じモデルを
            渡すこと(呼び出し側の責任。build_fn 自体は capture に含まれない)。
        run_id: 再現したい run の識別子(``results/runs/<run_id>``)。
        runs_root: run を探す/書き出す先。``None`` なら既定の `RUNS_ROOT`。
        time_limit: 制限時間を上書きしたい場合に指定。``None`` なら元の run が
            capture した ``limits/time`` をそのまま使う(記録が無ければ無制限)。

    Returns:
        新しく作られた run の ``run_id``。

    Raises:
        FileNotFoundError: 指定した ``run_id`` のディレクトリ/``meta.json`` が無い場合。
        ValueError: run は存在するが ``meta.capture.scip_params_diff`` が記録されて
            いない場合(``capture=False`` で求解した旧run、または capture 自体が
            失敗した run)。

    Example:
        ```python
        >>> import contextlib, io, tempfile
        >>> from pathlib import Path
        >>> from pyscipopt import Model, quicksum
        >>> from minlpkit.live import rerun, sweep
        >>> def build():
        ...     m = Model(); m.hideOutput()
        ...     x = {i: m.addVar(vtype="B", name=f"x{i}") for i in range(6)}
        ...     m.addCons(quicksum(x.values()) <= 3)
        ...     m.setObjective(quicksum((i + 1) * x[i] for i in x), "maximize")
        ...     return m
        >>> with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        ...     df = sweep(build, [{"limits/gap": 0.0}], name="doctest_rerun",
        ...                time_limit=5, runs_root=Path(tmp))
        ...     new_id = rerun(build, df["run_id"][0], runs_root=Path(tmp))
        >>> new_id != df["run_id"][0]
        True

        ```
    """
    root = runs_root if runs_root is not None else RUNS_ROOT
    run_dir = Path(root) / run_id
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"run が見つかりません: {run_id!r} ({meta_path})。runs_root の指定を確認してください。")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    capture = meta.get("capture")
    if not capture or "scip_params_diff" not in capture:
        raise ValueError(
            f"run {run_id!r} には capture.scip_params_diff が記録されていません。"
            "rerun は solve_with_monitor(..., capture=True) で記録された run にのみ使えます"
            "(capture=False で求解した旧runは再現できません)。")
    params_diff = dict(capture["scip_params_diff"])
    if time_limit is not None:
        params_diff.pop("limits/time", None)

    m = build_fn()
    m.hideOutput()
    m.setParam("timing/clocktype", 2)
    for k, v in params_diff.items():
        m.setParam(k, v)

    model_name = meta.get("model", "rerun")
    new_id = _unique_run_id(model_name, root)
    logger = RunLogger(
        new_id,
        meta=dict(model=model_name, title=f"rerun of {run_id}",
                  params=dict(time_limit=time_limit), rerun_of=run_id),
        root=root,
    )
    solve_with_monitor(m, time_limit=time_limit, logger=logger)
    return new_id
