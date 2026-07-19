"""診断ルールエンジン: 観測量 → 症状判定 → 改善提案 (Phase 3)

Phase 1-2 の可視化で得た観測量(metrics dict)を閾値ベースのルールに通し、
発火した症状ごとに「原因」「推薦する改善」「根拠(値と参照HTML)」を返す。
ルールは task.md の診断ルール表をコード化したもの。閾値は実測に基づく初期値。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Rule:
    """1つの診断ルール(症状→原因→推薦→根拠→直し方)。

    ``mk.RULES`` に ``Rule`` を追加すれば診断はプラガブルに拡張できる。``condition`` が
    metrics dict に対して True を返すと発火し、``evaluate`` の結果に含まれる。

    Attributes:
        id: ルール識別子。
        symptom: 観測される症状の説明。
        cause: 疑われる原因。
        recommendation: 推薦する改善。
        condition: ``metrics(dict) -> bool``。発火条件。
        evidence: ``metrics(dict) -> str``。発火根拠(実測値を埋めた文字列)。
        links: 参照する成果物HTMLのファイル名list。
        severity: ``good`` / ``warning`` / ``serious`` / ``critical`` のいずれか。
        recipe: 具体的な直し方(使う minlpkit 関数 + worked example)。
    """
    id: str
    symptom: str          # 観測される症状
    cause: str            # 疑われる原因
    recommendation: str   # 推薦する改善(Phase 4で実施)
    condition: Callable[[dict], bool]
    evidence: Callable[[dict], str]        # 発火根拠の文字列(実測値)
    links: list[str] = field(default_factory=list)  # 参照する成果物HTML
    severity: str = "warning"  # good/warning/serious/critical
    recipe: str = ""           # 具体的な直し方(使うminlpkit関数 + worked example)


def _get(m: dict, key: str, default=None):
    v = m.get(key, default)
    return default if v is None else v


# --- ルール定義(task.md の診断ルール表をコード化) ---
RULES: list[Rule] = [
    Rule(
        id="weak_relaxation",
        symptom="特定の非線形制約に緩和違反が集中(かつ空間分枝が多い)",
        cause="その制約の凸緩和が支配的ボトルネック(非凸項の緩和が緩い)",
        recommendation="ボトルネック制約の区分線形近似・凸包再定式化・変数境界タイト化",
        condition=lambda m: _get(m, "bottleneck_rel_viol", 0) >= 0.5
                            and _get(m, "spatial_share", 0) >= 0.3,
        evidence=lambda m: f"支配ボトルネック={m.get('bottleneck_type')}"
                           f"(相対違反{m.get('bottleneck_rel_viol', 0):.2f})、"
                           f"空間分枝の双対寄与{m.get('spatial_share', 0) * 100:.0f}%",
        links=["violation.html", "attribution.html"],
        severity="serious",
        recipe="整数×連続の積は mk.linearize_product(m,y,x,...) で厳密線形化。非線形1変数は "
               "mk.pwl_sos2(m,x,brks,vals) で区分線形化。例: scheduling_plant(n·s)→improve_linearize.html, sos.html",
    ),
    Rule(
        id="wide_term_range",
        symptom="非線形項の値域(区間演算)が広い",
        cause="変数境界が緩く、凸緩和が広く張らざるを得ない",
        recommendation="該当項の変数境界タイト化・区分線形化(spatial分枝前の前処理)",
        condition=lambda m: _get(m, "widest_term_rel", 0) >= 1.5,
        evidence=lambda m: f"最大値域項={m.get('widest_term')}"
                           f"(相対幅{m.get('widest_term_rel', 0):.2f})",
        links=["interval.html"],
        severity="warning",
        recipe="mk.linearize_product で該当積を厳密化、または変数境界をタイト化してから spatial 分枝。"
               "例: interval.html, improve_linearize.html",
    ),
    Rule(
        id="dual_stall",
        symptom="双対境界の改善が停滞(gapが残る)",
        cause="緩和が弱く双対境界が上がりきらない",
        recommendation="有効不等式の追加・変数境界タイト化・Big-M排除で緩和強化",
        condition=lambda m: _get(m, "n_stalls", 0) >= 1 and _get(m, "gap", 0) >= 0.05,
        evidence=lambda m: f"停滞区間{m.get('n_stalls')}個、最終gap{m.get('gap', 0) * 100:.1f}%",
        links=["attribution.html", "plant_dashboard.html"],
        severity="warning",
        recipe="有効不等式の追加・変数境界タイト化・Big-M排除で緩和を強化。効果は mk.compare_variants で検証。"
               "例: attribution.html",
    ),
    Rule(
        id="numerical_scale",
        symptom="係数の絶対値レンジが桁違い / Big-M候補あり(presolve後も残存)",
        cause="数値的不安定(丸め誤差でソルバーが迷走)。SCIPのpresolveで締まらない残存分",
        recommendation="スケーリング、Big-MのIndicator/SOS制約化、係数の再定式化",
        # presolve後の残存スケールで判断。SCIPが自動で締める分は発火させない。
        # 比の閾値は真の悪条件(1e6)。自然なコスト差(~1e3)は数値問題ではないので拾わない
        condition=lambda m: _get(m, "residual_coef_ratio", 0) >= 1e6
                            or _get(m, "residual_bigm_count", 0) >= 1,
        evidence=lambda m: f"presolve後の係数比={m.get('residual_coef_ratio', 0):.3g}"
                           f"(presolve前{m.get('coef_ratio', 0):.3g})、"
                           f"残存Big-M{m.get('residual_bigm_count', 0)}件",
        links=["static_plant.html", "static_uc.html"],
        severity="warning",
        recipe="Big-Mを実bound/Indicator/SOSに置換。半連続on-offは Indicator、区分線形は mk.pwl_sos2。"
               "条件数は viz.static_diag.matrix_condition/scip_basis_condition で確認。例: sos.html, condition.html",
    ),
    # 対称性はSCIPが内蔵の対称性処理(usesymmetry既定ON)で自動対応するため、
    # 手動の辞書式除去は通常不要 → 推薦としては出さず、情報として severity=good で軽く示す。
    # 実測でもmakespan/グラフ彩色は既定SCIPが1ノードで解け、手動除去は無効〜悪化だった。
    Rule(
        id="symmetry_info",
        symptom="入替可能な変数群(対称性)を検出(参考情報)",
        cause="対称解は探索木を膨張させ得るが、SCIP内蔵の対称性処理が既定で対応する",
        recommendation="通常は対応不要(SCIPが自動処理)。usesymmetryを無効化した運用でのみ辞書式除去が有効",
        condition=lambda m: _get(m, "sym_sound", False)
                            and _get(m, "largest_sym_group", 0) >= 3,
        evidence=lambda m: f"対称群{m.get('n_sym_groups', 0)}個・最大{m.get('largest_sym_group', 0)}"
                           "(全線形で健全判定)。SCIP既定で自動処理されるため手動除去は通常不要",
        links=["symmetry.html"],
        severity="good",
        recipe="通常は対応不要(SCIP既定で自動)。あえて行うなら辞書式順序制約。例: symmetry.html",
    ),
    Rule(
        id="decomposable",
        symptom="制約-変数がブロック構造 + 少数の結合制約",
        cause="ブロックごとに分解可能な構造(結合制約が境界)",
        recommendation="ベンダーズ分解 / Dantzig-Wolfe分解(結合制約を主問題に)",
        condition=lambda m: _get(m, "max_linking_groups", 0) >= 4
                            and _get(m, "n_heavy_linking", 99) <= 3,
        evidence=lambda m: f"最大結合制約が{m.get('max_linking_groups')}グループにまたがる、"
                           f"重結合制約は{m.get('n_heavy_linking')}本のみ",
        links=["static_plant.html"],
        severity="good",
        recipe="mk.benders(master_build, subproblem_solve) で分解、または mk.column_generation/"
               "mk.price_and_branch(pricing_fn)。例: benders.html, bnp.html",
    ),
]


def evaluate(metrics: dict) -> list[dict]:
    """観測量 dict に ``RULES`` を適用し、発火したルールを重要度順で返す。

    Args:
        metrics: ``collect_metrics`` が返す観測量 dict。

    Returns:
        list[dict]: 発火したルール。``critical`` → ``serious`` → ``warning`` → ``good``
        の順。各要素は ``id`` / ``symptom`` / ``cause`` / ``recommendation`` /
        ``evidence`` / ``links`` / ``severity`` / ``recipe`` を持つ。

    Example:
        ```python
        >>> import minlpkit as mk
        >>> fired = mk.evaluate({"n_stalls": 2, "gap": 0.3})
        >>> any(f["id"] == "dual_stall" for f in fired)
        True

        ```
    """
    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3}
    fired = []
    for r in RULES:
        try:
            if r.condition(metrics):
                fired.append(dict(
                    id=r.id, symptom=r.symptom, cause=r.cause,
                    recommendation=r.recommendation, evidence=r.evidence(metrics),
                    links=r.links, severity=r.severity, recipe=r.recipe))
        except Exception:
            continue
    fired.sort(key=lambda f: order.get(f["severity"], 9))
    return fired
