"""pytest 共通設定: samples/ を import パスに追加(facility 等のサンプルを使うテスト用)。"""
import sys
from pathlib import Path

_SAMPLES = Path(__file__).resolve().parent.parent / "samples"
if str(_SAMPLES) not in sys.path:
    sys.path.insert(0, str(_SAMPLES))
