"""Run 条件の自動キャプチャ(最適化 MLOps の土台)

求解直前のモデルとその実行環境から「run を再現するのに必要な条件」を集める。
SCIP パラメータの非デフォルト差分・モデル指紋・環境・git SHA を dict にまとめ、
`solve_with_monitor` が `meta.json` の ``capture`` キーへ自動保存する。

各項目は独立に ``try/except`` で守られ、取得に失敗しても求解を止めない
(欠けた項目はキーごと省略される)。
"""

from __future__ import annotations

import platform
import subprocess
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pyscipopt import Model

# SCIP の非線形系制約ハンドラ名。これ以外は線形として数える。
_NONLINEAR_HANDLERS = {"nonlinear", "quadratic", "soc", "abspower", "bivariate", "expr"}


def _scip_params_diff(model: Model) -> dict:
    """デフォルトと異なる値になっている SCIP パラメータの ``{name: value}``。

    素の ``Model()`` の `getParams` をデフォルト基準とし、対象モデルの現在値と
    差があるものだけを返す(通常は数個〜数十個)。
    """
    base = Model().getParams()
    cur = model.getParams()
    return {k: v for k, v in cur.items() if base.get(k) != v}


def _fingerprint(model: Model) -> dict:
    """presolve 前のモデル指紋(変数/制約の型別内訳・目的の向き・名前)。"""
    nbin = nint = ncont = 0
    for v in model.getVars():
        t = v.vtype()
        if t == "BINARY":
            nbin += 1
        elif t == "INTEGER":
            nint += 1
        else:  # CONTINUOUS / IMPLINT
            ncont += 1
    by_handler: dict[str, int] = {}
    nlin = nnonlin = 0
    conss = model.getConss()
    for con in conss:
        h = con.getConshdlrName()
        by_handler[h] = by_handler.get(h, 0) + 1
        if h in _NONLINEAR_HANDLERS:
            nnonlin += 1
        else:
            nlin += 1
    return {
        "name": model.getProbName(),
        "objective_sense": model.getObjectiveSense(),
        "n_vars": model.getNVars(),
        "n_bin": nbin,
        "n_int": nint,
        "n_cont": ncont,
        "n_conss": len(conss),
        "n_linear": nlin,
        "n_nonlinear": nnonlin,
        "conss_by_handler": by_handler,
    }


def _env(model: Model) -> dict:
    """実行環境(minlpkit/Python/PySCIPOpt/SCIP バージョン・OS)。"""
    env = {
        "python": platform.python_version(),
        "os": platform.platform(),
        "scip": str(model.version()),
    }
    for dist, key in (("minlpkit", "minlpkit"), ("pyscipopt", "pyscipopt")):
        try:
            env[key] = version(dist)
        except PackageNotFoundError:
            pass
    return env


def _git_sha() -> str | None:
    """現在の作業ディレクトリの git HEAD の SHA。git 不在/非リポジトリなら ``None``。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path.cwd(), capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.strip() or None


def capture_run_conditions(model: Model) -> dict:
    """求解直前のモデルから run 再現用の条件を集めて dict で返す。

    ``solve_with_monitor(..., logger=...)`` が内部で呼び、結果を ``meta.json`` の
    ``capture`` キーに保存する。単体でも使える(下記 Example)。各項目は独立に
    ``try/except`` で守られ、取得に失敗した項目はキーごと省略される
    (キャプチャ全体が求解を止めることはない)。

    Args:
        model: 求解直前(presolve 前)の ``pyscipopt.Model``。パラメータ差分を
            正しく拾うため、``setParam`` を済ませた後・``optimize`` の前に渡す。

    Returns:
        次のキーを持つ dict(取得できたものだけ):

        - ``scip_params_diff``: デフォルトと異なる SCIP パラメータの ``{name: value}``。
        - ``fingerprint``: 変数/制約の型別内訳・目的の向き・モデル名。
        - ``env``: minlpkit/Python/PySCIPOpt/SCIP バージョンと OS。
        - ``git_sha``: 作業ディレクトリの git HEAD(取れた場合のみ)。

    Example:
        ```python
        >>> from pyscipopt import Model
        >>> from minlpkit.live import capture_run_conditions
        >>> m = Model()
        >>> _ = m.addVar(vtype="B")
        >>> m.setParam("limits/time", 5.0)
        >>> cap = capture_run_conditions(m)
        >>> cap["scip_params_diff"]["limits/time"]
        5.0
        >>> cap["fingerprint"]["n_bin"]
        1
        >>> "python" in cap["env"]
        True

        ```
    """
    cap: dict = {}
    for key, fn in (
        ("scip_params_diff", lambda: _scip_params_diff(model)),
        ("fingerprint", lambda: _fingerprint(model)),
        ("env", lambda: _env(model)),
        ("git_sha", _git_sha),
    ):
        try:
            val = fn()
        except Exception:  # noqa: BLE001 - キャプチャ失敗は求解を止めない
            continue
        if val is not None:
            cap[key] = val
    return cap
