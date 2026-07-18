---
name: minlp-diagnose
description: MINLPの収束停滞・数値不安定・構造の診断チェックリストと、観測量→改善提案のルール適用手順。
---

# minlp-diagnose: 診断ルールと改善提案

Phase 1-2 の可視化で得た観測量を診断ルールに通し、「どの改善が向いているか」を機械的に提示する。

## 実行

```
# CLI(モデルキー指定)
uv run python experiments/run_diagnose.py --model {plant|uc|facility|parallel} --time <秒>
  → results/diagnose_<model>.html

# ライブラリAPI(推奨・model非依存)
import minlpkit as mk
report = mk.analyze(lambda: build_model(), name="plant", time_limit=20,
                    interval_terms_fn=evaluate_terms)  # interval_terms_fnは任意
report.summary(); report.dashboard("results/report.html")
```

エンジン: `viz/diagnose.py`(ルール定義 `RULES` と `evaluate(metrics)`、`mk.RULES`/`mk.evaluate`でも公開)。
観測量収集: `minlpkit.collect_metrics(build_fn, ...)`(Phase 1-2の収集器を統合、model非依存)。
一気通貫デモ: `uv run python demo.py`(可視化→診断→改善→再検証)。

## 診断ルール表(コード化済み。閾値は実測ベースの初期値)

| ルールid | 症状(観測) | 原因 | 推薦する改善 | 主な観測量 |
| --- | --- | --- | --- | --- |
| weak_relaxation | 非線形制約に緩和違反集中+空間分枝多 | 凸緩和が支配的ボトルネック | 区分線形近似・凸包再定式化・境界タイト化 | bottleneck_rel_viol≥0.5, spatial_share≥0.3 |
| wide_term_range | 非線形項の値域(区間演算)が広い | 変数境界が緩い | 境界タイト化・区分線形化 | widest_term_rel≥1.5 |
| dual_stall | 双対境界停滞(gap残る) | 緩和が弱い | 有効不等式・境界タイト化・Big-M排除 | n_stalls≥1, gap≥0.05 |
| numerical_scale | 係数レンジ桁違い/Big-M候補 | 数値不安定 | スケーリング・Indicator/SOS化 | coef_ratio≥1e3 or bigm_count≥1 |
| symmetry | 入替可能な変数群 | 対称解で木が膨張 | 辞書式順序制約 | sym_sound かつ largest_sym_group≥3 |
| decomposable | ブロック構造+少数結合制約 | 分解可能 | ベンダーズ/DW分解 | max_linking_groups≥4, n_heavy_linking≤3 |

## SCIP-aware原則(厳守)— SCIPが自動処理する分は推薦しない

現代のSCIPはpresolve/内蔵対称性処理/FBBTが強力で、多くの「教科書的改善」を自動で解消する。
診断は**SCIPが直せない残存分だけ**を推薦する(実測で確かめた挙動):

- **Big-M/数値スケール**: presolve**前**の係数比ではなく、`residual_scale`(presolve**後**)で判断する。
  緩いBig-M(比1e5)はpresolveで比1.0/bigm 0に自動解消される → 推薦しない。
  残存Big-M(uc の ramp pmax=400 等)や真の悪条件(残存比≥1e6、plantの≈4.5e7)のみ発火。
  比の閾値は1e6(自然なコスト差~1e3は数値問題ではないので拾わない)。
- **対称性**: SCIPは`misc/usesymmetry`既定ONで自動対応。実測でmakespan・グラフ彩色は既定SCIPが
  1ノードで解け、手動の辞書式除去は無効〜悪化だった。→ 推薦(warning)ではなく**情報(good)**として
  「SCIPが自動処理・通常対応不要」と示す(`symmetry_info`ルール)。
- **変数境界タイト化**: SCIPのFBBTが基本的なタイト化を自動実施。plantで手動タイト化は
  ルート境界52.13→52.25の微増のみ。単純なFBBT範囲は推薦しない。
- **残る真の律速**: 非凸緩和の弱さ(plantの74%gap、weak_relaxation)はSCIPが自動解消**しない** →
  これは正当な推薦として残す。

## 重要な健全性ルール(厳守)

- **対称性検出は非線形制約があると不確定**。`viz/symmetry.py` は線形制約しか見られず、
  ジョブ間の定数差(非線形制約内)を無視して偽陽性を出す。全線形モデルのみ `sound=True`。
  診断ルール `symmetry` は `sym_sound` が真のときだけ発火させる(plantでは出さない=SCIPの
  「no symmetry present」と整合)。SCIPの対称性生成子はPySCIPOptから取得不可。
- 観測量が取れないモデルではそのルールを発火させない(例: 非線形なし→違反ルールは対象外)。
  スキップではなく「その症状は該当しない」ことの正しい反映。

## 新しいルールの追加

`viz/diagnose.py` の `RULES` に `Rule(...)` を1つ足す(condition/evidence/links/severity)。
閾値の根拠は必ず実モデルでの観測に基づく。`links` は参照する成果物HTML名。
