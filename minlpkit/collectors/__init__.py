"""minlpkit.collectors — 観測量収集器と診断ルール(旧 viz/ の実体)。

Phase 1-4 の収集器(収束モニタの帰属・空間分枝木・違反・静的診断・対称性検出)と
診断ルールエンジンを minlpkit 配下に移設したもの。これにより minlpkit は viz/ に
依存せず単体で成立する(別プロジェクトから import 可能)。

リポジトリ内の既存 CLI (run_*.py) は `viz/` 側の後方互換シム
(`from minlpkit.collectors.X import *`)経由で無修正のまま動く。
"""
