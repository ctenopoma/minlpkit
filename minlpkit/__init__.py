"""minlpkit — MINLPの可視化・診断・改善検証を一体化したPySCIPOptラッパー。

Phase 1-4の成果(収束モニタ・空間分枝/違反/静的診断・診断ルール・before/after比較)を
model非依存のパイプラインAPIに再構成したもの。

主要API:
    analyze(build_fn, time_limit, ...) -> Report   # 観測量収集 + 診断
    Report.dashboard(path)                          # 統合ダッシュボードHTML
    compare_variants(variants, ...) -> DataFrame    # 改善のbefore/after比較
    RULES, evaluate                                 # 診断ルール(プラガブル)
    sweep(build_fn, param_sets, ...) -> DataFrame   # パラメータスイープ(要 viz extras)
    rerun(build_fn, run_id, ...) -> str             # 記録条件からの再現実行(要 viz extras)
"""

from .collectors.diagnose import RULES, Rule, evaluate

from .compare import compare_variants
from .frameworks import benders, column_generation, price_and_branch
from .gpu import cuopt_concurrent, cuopt_warmstart
from .pipeline import Report, analyze, collect_metrics
from .transforms import linearize_product, perspective_quadratic, pwl_sos2

__all__ = ["analyze", "collect_metrics", "Report", "compare_variants",
           "RULES", "Rule", "evaluate", "linearize_product", "perspective_quadratic",
           "pwl_sos2", "column_generation", "price_and_branch", "benders",
           "cuopt_warmstart", "cuopt_concurrent", "sweep", "rerun"]

_LAZY_LIVE = {"sweep", "rerun"}


def __getattr__(name: str):
    """`sweep` / `rerun` は `minlpkit.live`(要 viz extras)から遅延importする。

    コアの `import minlpkit` を flask/plotly 無しで動かし続けるため、
    実際にこれらの属性へアクセスしたときだけ `minlpkit.live` を読み込む。
    """
    if name in _LAZY_LIVE:
        from . import live
        return getattr(live, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
