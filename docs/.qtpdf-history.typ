// 改訂履歴。git の履歴から自動生成。表紙の次、目次の前に置く。
#{
  set page(numbering: none)
  heading(level: 1, outlined: false, numbering: none)[改訂履歴]
  v(0.6em)
  table(
    columns: (auto, auto, 1fr, auto),
    inset: (x: 8pt, y: 6pt),
    stroke: 0.5pt + luma(120),
    fill: (x, y) => if y == 0 { luma(235) } else { none },
    table.header([版数], [日付], [改訂内容], [作成]),
    [d345cd4], [2026-07-19], [initial commit], [ctenopoma],
    [29c2018], [2026-07-19], [Add automatic run-condition capture to solve\_with\_monitor (C1)], [ctenopoma],
    [e1b5a41], [2026-07-19], [Add SCIP parameter sweep + rerun (Phase 10 C3)], [ctenopoma],
    [eefcd8c], [2026-07-19], [Phase 11.4-11.6: mk.cuopt\_warmstart API + gpu\_primal診断ルール + GPUダッシュボード], [ctenopoma],
    [035d244], [2026-07-19], [Phase 11.7: GPU実験のライブモニタ統合(--live) + manual診断表更新], [ctenopoma],
    [bec7177], [2026-07-19], [Phase 11.8: 常駐型ハイブリッド mk.cuopt\_concurrent(cuOpt並走+mid-solve注入)], [ctenopoma],
    [cf21159], [2026-07-19], [Phase 11.9-11.10: cuPDLP検証 + xlスケール実験 + concurrent注入の診断/ガード], [ctenopoma],
    [2deb0ee], [2026-07-19], [Phase 11.11: GPU無し環境への配慮(cuopt\_available + 案内付きエラー + 設計明文化)], [ctenopoma],
    [ac23d7d], [2026-07-20], [Phase 12: 診断センサス + ハンズオンnotebook 2本を追加・公開], [ctenopoma],
    [28c51ba], [2026-07-20], [update designe], [ctenopoma],
    [3a3f27d], [2026-07-20], [Phase 11.2: cuOpt HTTP バックエンド(リモートGPUサーバ + Docker運用)], [ctenopoma],
    [21bbe6f], [2026-07-20], [Add practitioner playbook (symptom-driven) + reorganize docs nav], [ctenopoma],
  )
  pagebreak(weak: false)
}
