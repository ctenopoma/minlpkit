"""pytest 共通設定: samples/ とそのカテゴリ別サブディレクトリを import パスに追加。

samples/ は 2026-07 にカテゴリ別サブディレクトリ構成(scheduling/ energy_and_microgrid/
packing_and_cutting/ 等)へ再編された。テストは従来どおりフラットなモジュール名
(``from gap_large import build_model`` 等)で参照できるよう、全サブディレクトリを
sys.path に載せる。
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_SAMPLES = _ROOT / "samples"
for _p in [_SAMPLES, *sorted(d for d in _SAMPLES.iterdir() if d.is_dir() and d.name != "__pycache__")]:
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
