"""静的診断: 数値スケール(Big-M検出)と制約-変数の構造 (Phase 2.c)

solve前にモデルから静的に取れる情報で数値的健全性と分解適性を診断する。
- 係数スケール: 線形制約の係数・目的係数・RHS・変数境界の絶対値レンジ。
  桁違い(max/min比が大)= 数値不安定の兆候。突出した大係数 = Big-M候補。
- 構造: 制約×変数の接続行列(getConsVarsは非線形制約でも動く)。RCMで並べ替えて
  ブロック対角性を可視化。多数の変数群にまたがる制約 = 結合制約(分解の境界)。
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from pyscipopt import Model
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import reverse_cuthill_mckee

_INF = 1e19


def extract_coefficients(model: Model) -> pd.DataFrame:
    """係数・目的・RHS・境界の絶対値を出所付きで集める。"""
    rows: list[dict] = []

    # 線形制約の係数と RHS/LHS
    for c in model.getConss():
        if not c.isLinear():
            continue
        for v, coef in model.getValsLinear(c).items():
            if coef != 0:
                rows.append(dict(source="制約係数", magnitude=abs(coef), name=c.name))
        for side_getter, label in ((model.getRhs, "RHS"), (model.getLhs, "LHS")):
            try:
                s = side_getter(c)
            except Exception:
                continue
            if s is not None and abs(s) < _INF and s != 0:
                rows.append(dict(source="RHS/LHS", magnitude=abs(s), name=c.name))

    # 目的係数
    for v in model.getVars():
        o = v.getObj()
        if o != 0:
            rows.append(dict(source="目的係数", magnitude=abs(o), name=v.name))

    # 変数境界(有限のもの)
    for v in model.getVars():
        for b in (v.getLbGlobal(), v.getUbGlobal()):
            if b is not None and 0 < abs(b) < _INF:
                rows.append(dict(source="変数境界", magnitude=abs(b), name=v.name))

    return pd.DataFrame(rows)


def scale_summary(df: pd.DataFrame, bigm_ratio: float = 100.0) -> dict:
    """全体のスケール指標と Big-M 候補を返す。"""
    if df.empty:
        return dict(min=None, max=None, ratio=None, bigm=[])
    mags = df["magnitude"]
    mn, mx = float(mags.min()), float(mags.max())
    ratio = mx / mn if mn > 0 else None
    med = float(mags.median())
    # 中央値の bigm_ratio 倍を超える大係数(制約係数/境界)= Big-M候補
    cand = df[(df["magnitude"] > med * bigm_ratio) &
              (df["source"].isin(["制約係数", "変数境界"]))]
    bigm = (cand.sort_values("magnitude", ascending=False)
            .drop_duplicates("name").head(10)[["name", "source", "magnitude"]]
            .to_dict("records"))
    return dict(min=mn, max=mx, ratio=ratio, median=med, bigm=bigm)


def matrix_condition(model: Model) -> dict:
    """線形制約の係数行列 A の条件数 κ(A)=σ_max/σ_min(numpy SVD、solve前に計算可能)。

    ノートの Model Analyzer が指す κ(A)=‖A‖·‖A⁻¹‖ の実体。大きいほど悪条件=
    丸め誤差でソルバーが迷走しやすい。緩いBig-Mは A を悪条件化する。
    """
    import numpy as np
    vars_ = model.getVars()
    vidx = {v.name: i for i, v in enumerate(vars_)}
    rows = []
    for c in model.getConss():
        if not c.isLinear():
            continue
        vals = model.getValsLinear(c)
        if not vals:
            continue
        row = np.zeros(len(vars_))
        for vn, coef in vals.items():
            if vn in vidx:
                row[vidx[vn]] = coef
        rows.append(row)
    if not rows:
        return dict(kappa=None, shape=(0, 0))
    A = np.array(rows)
    A = A[:, np.any(A != 0, axis=0)]  # 全ゼロ列除去
    sv = np.linalg.svd(A, compute_uv=False)
    sv = sv[sv > 1e-12]
    return dict(kappa=float(sv[0] / sv[-1]), shape=A.shape)


def scip_basis_condition(model: Model) -> float | None:
    """SCIPが報告する最適LP基底の条件数(getCondition、solve後)。実際の数値不安定度。"""
    model.hideOutput()
    model.setParam("limits/nodes", 1)
    model.optimize()
    try:
        k = model.getCondition()
        return float(k) if k and k > 0 else None
    except Exception:
        return None


def residual_scale(model: Model) -> dict:
    """presolve後に残る係数スケールを返す(SCIPが自動で締めた分を除いた残存)。

    presolve前の係数比が大きくても、SCIPのpresolveが自動でBig-Mを締める場合は
    残存比が小さくなる。診断はこの残存で判断すべき(自動処理される分は推薦しない)。
    """
    model.hideOutput()
    try:
        model.presolve()
    except Exception:
        pass
    df = extract_coefficients(model)
    return scale_summary(df)


def constraint_ratio(model: Model) -> pd.DataFrame:
    """線形制約ごとの係数 max/min 比(悪条件な制約の特定)。"""
    rows = []
    for c in model.getConss():
        if not c.isLinear():
            continue
        mags = [abs(v) for v in model.getValsLinear(c).values() if v != 0]
        if len(mags) >= 2:
            rows.append(dict(constraint=c.name, min_coef=min(mags), max_coef=max(mags),
                             ratio=max(mags) / min(mags)))
    return pd.DataFrame(rows).sort_values("ratio", ascending=False) if rows else pd.DataFrame()


def incidence(model: Model) -> tuple[np.ndarray, list[str], list[str]]:
    """制約×変数の接続行列(0/1)と、制約名・変数名を返す。"""
    vars_ = model.getVars()
    vidx = {v.name: i for i, v in enumerate(vars_)}
    conss = model.getConss()
    M = np.zeros((len(conss), len(vars_)), dtype=np.int8)
    cnames = []
    for r, c in enumerate(conss):
        cnames.append(c.name)
        try:
            cvars = model.getConsVars(c)
        except Exception:
            cvars = []
        for v in cvars:
            j = vidx.get(v.name)
            if j is not None:
                M[r, j] = 1
    return M, cnames, [v.name for v in vars_]


def reorder_blocks(M: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """RCM(逆Cuthill-McKee)で行・列を並べ替え、ブロック対角性を出す。

    制約-変数の二部グラフを1つの隣接行列に埋め込んで RCM を適用する。
    返り値: (行順, 列順, 並べ替え後の行列)
    """
    nr, nc = M.shape
    n = nr + nc
    # 二部グラフの隣接行列 [[0, M],[M^T, 0]]
    A = np.zeros((n, n), dtype=np.int8)
    A[:nr, nr:] = M
    A[nr:, :nr] = M.T
    perm = reverse_cuthill_mckee(csr_matrix(A), symmetric_mode=True)
    row_perm = [p for p in perm if p < nr]
    col_perm = [p - nr for p in perm if p >= nr]
    Mr = M[np.ix_(row_perm, col_perm)]
    return np.array(row_perm), np.array(col_perm), Mr


def linking_constraints(model: Model, group_of=None) -> pd.DataFrame:
    """各制約が何個の変数グループにまたがるかを数え、結合制約を特定する。

    group_of(var_name)->group。省略時は変数名の末尾トークン(J1,M2等)をグループとみなす。
    またがるグループ数が多い制約 = 分解の境界になる結合制約。
    """
    if group_of is None:
        def group_of(name: str) -> str:
            return name.rsplit("_", 1)[-1]
    rows = []
    for c in model.getConss():
        try:
            cvars = model.getConsVars(c)
        except Exception:
            cvars = []
        groups = {group_of(v.name) for v in cvars}
        rows.append(dict(constraint=c.name, n_groups=len(groups), n_vars=len(cvars),
                         groups=",".join(sorted(groups))))
    # 制約が1本もないモデル(例: 変数境界のみで目的関数を定義するairline_overbooking)では
    # rows=[] となり、pd.DataFrame([]) は列を持たないため sort_values("n_groups") がKeyErrorになる。
    if not rows:
        return pd.DataFrame(columns=["constraint", "n_groups", "n_vars", "groups"])
    return pd.DataFrame(rows).sort_values("n_groups", ascending=False)
