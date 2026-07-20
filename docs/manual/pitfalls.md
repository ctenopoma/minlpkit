# 制約・既知の落とし穴(利用者目線)

[← 利用マニュアル目次](index.md)

`FINDINGS.md` の要点。「教科書的改善の多くを現代の SCIP は自動でやる」ことに注意。

## SCIP が自動でやること(手動で推薦しない)

「教科書的改善の多くを現代の SCIP は自動でやる」。対称性除去・被約コスト固定・Perspective再定式化の
3手法について、診断の考え方・実測効果・使い所の詳細は
[手法ガイド 参考: SCIPが自動でやること](../playbook/10-reference-scip-handles.md) を参照。

要点のみ: **緩い Big-M** は presolve が自動でタイト化する(手動対応は典型例では不要)。診断は
presolve **後**の残存(`residual_scale`)で判断し、比の閾値は真の悪条件 1e6(自然なコスト差 ~1e3
は数値問題ではない)にしてある。

## かえって悪化する「改善」

- 有効不等式 $n \cdot s \ge \text{demand}$ を素朴に足すと、$n \cdot s$ 自体が双線形なので**新たな非凸制約の追加**になり緩和が緩む。
- **perspective_quadratic**: 理論上は凸包を締めるが、SCIP は右辺の双線形を McCormick 緩和するため
  素の分枝限定ではむしろ −49% 悪化。既定 SCIP では素の凸二次下界の方が有利。**部品として提供するが常用非推奨**。

## 測定方法論(交絡を避ける)

- **時間制限での比較は探索動学に交絡される**(制約追加でノード/秒が変わる)。定式化の質は
  **ルート双対境界**(`compare_variants` の `root_dual`)で測ると交絡がない。
- ある定式化の効果を分離するには、補償機構(presolve/separating/対称性/伝播)を明示的に OFF にして
  素の分枝限定で比べる。現代 SCIP は小規模 MILP を大抵ルート1ノードで解くので、効果を見たいなら
  効果が現れる規模/構造の題材を作る(本リポジトリの fixed_charge 8施設・graph_coloring 等)。

## price_and_branch は上界のみ

- `price_and_branch` は「生成列上の制限主問題を整数で解く」ため、返す整数解は真の整数最適の**上界**
  ($z_{\mathrm{PB}} \ge z^\star$)であって最適保証ではない。厳密な整数最適には pricing を分枝ノードで呼ぶ完全な
  branch-and-price が要る。`lp_lb == int_obj` が成り立てば最適性が証明される。

## PySCIPOpt の API 落とし穴

- `getValsLinear(cons)` のキーは**変数名の文字列**。`Variable` に `getName()` は無い(`.name` を使う)。
- 分枝情報は `NODEBRANCHED` で取る(`NODEFOCUSED` では `getParentBranchings()` が空)。
- `getSlack` は非線形制約に非対応 → 違反は `getNlRowSolFeasibility(nlrow, sol)`(負=違反量)。
- `build_fn()` の一時 Model はローカル変数に保持する(反復中に GC されると PySCIPOpt が segfault)。
- Windows の SCIP クロックは1秒粒度 → モニタは Python の `perf_counter` で記録する。
