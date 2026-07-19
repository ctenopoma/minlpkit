// live_rules.js — ライブ診断・ライブ指標の純関数群 (Phase 10 B)
//
// SCIP探索の逐次イベント列(events.jsonlの各行 = {time, dual, primal, gap, event, nodes})
// から、ブラウザ側で「今どういう症状が出ているか」を判定する。ここに書く判定は
// collectors/attribution.detect_stalls などのオフライン診断のごく一部の簡易ライブ版であり、
// 全診断ルール(mk.RULES)を代替するものではない(バナー文言にもその旨を明記する)。
//
// ブラウザ(<script src="/live_rules.js">経由でグローバル関数として読み込み)と
// Node(`require('./live_rules.js')`、tests/js/live_rules.test.js)の両方から
// 同一の関数定義を使う。コピペの二重管理を避けるための唯一の実体。
(function (root) {
  'use strict';

  // --- 内部ヘルパー ---

  // dual boundは非減少とみなし累積最大を取ってから、時刻tでの値を線形補間する。
  // (SCIPの探索過程で稀に生じる数値的な後退ノイズを除くため)
  function _monotoneDualSampler(evs) {
    let maxSoFar = -Infinity;
    const mono = evs.map(e => {
      maxSoFar = Math.max(maxSoFar, e.dual);
      return maxSoFar;
    });
    return function (t) {
      if (t <= evs[0].time) return mono[0];
      const last = evs.length - 1;
      if (t >= evs[last].time) return mono[last];
      for (let i = 0; i < last; i++) {
        const ta = evs[i].time, tb = evs[i + 1].time;
        if (ta <= t && t <= tb) {
          if (tb === ta) return mono[i + 1];
          const f = (t - ta) / (tb - ta);
          return mono[i] + (mono[i + 1] - mono[i]) * f;
        }
      }
      return mono[last];
    };
  }

  function _lastGap(events) {
    for (let i = events.length - 1; i >= 0; i--) {
      if (events[i].gap != null) return events[i].gap;
    }
    return null;
  }

  // --- 症状検出(バナー用) ---

  /**
   * dual_stall: 双対境界の改善が鈍化している区間を検出する(注意/黄)。
   *
   * 判定: 経過時間の直近30%(最低20秒)の窓での改善レートが、全体平均レートの
   * 50%未満、かつ現在のgapが5%以上のとき発火する。collectors/attribution.detect_stalls
   * (オフライン・時間グリッド版)と同じ思想のライブ簡易版(全求解イベントでなく現在までの
   * イベント列だけで判定するため、確定判定ではない)。
   *
   * @param {Array<object>} events - {time, dual, gap, ...} の列(時刻昇順)。
   * @param {number} [now] - 現在時刻(省略時は最後のイベントのtime)。
   * @returns {{kind:string, severity:string, message:string, windowRate:number, overallRate:number, gap:number}|null}
   */
  function detectLiveStall(events, now) {
    const evs = (events || []).filter(e => e.dual != null && e.time != null)
      .slice().sort((a, b) => a.time - b.time);
    if (evs.length < 2) return null;
    const t0 = evs[0].time;
    const t1 = now != null ? now : evs[evs.length - 1].time;
    const elapsed = t1 - t0;
    if (elapsed <= 0) return null;

    const windowLen = Math.max(elapsed * 0.3, 20);
    if (windowLen >= elapsed) return null; // まだ「窓 < 全体」を作れるほど経過していない

    const gap = _lastGap(events);
    if (gap == null || gap < 0.05) return null;

    const sample = _monotoneDualSampler(evs);
    const dualStart = sample(t0), dualEnd = sample(t1);
    const overallRate = (dualEnd - dualStart) / elapsed;

    const winStart = t1 - windowLen;
    const dualWinStart = sample(winStart);
    const windowRate = (dualEnd - dualWinStart) / windowLen;

    let stalled;
    if (overallRate > 0) {
      stalled = windowRate < 0.5 * overallRate;
    } else {
      // 全体として全く改善していない場合、窓内改善が非正なら停滞とみなす
      stalled = windowRate <= 0;
    }
    if (!stalled) return null;

    return {
      kind: 'dual_stall',
      severity: 'warning',
      windowRate, overallRate, gap,
      message: `双対境界の改善が鈍化(直近${windowLen.toFixed(0)}s区間のレートが全体平均の50%未満、gap ${(gap * 100).toFixed(1)}%)。`
        + ' これはライブ簡易判定(全診断はmk.analyzeで実施。改善はlinearize_product等、recipe参照)。',
    };
  }

  /**
   * no_incumbent: 経過30秒でincumbentイベントが1件も無い(注意/黄)。
   *
   * @param {Array<object>} events
   * @param {number} [now]
   * @returns {{kind:string, severity:string, message:string, elapsed:number}|null}
   */
  function detectNoIncumbent(events, now) {
    const evs = (events || []).filter(e => e.time != null);
    if (!evs.length) return null;
    const t0 = evs[0].time;
    const t1 = now != null ? now : evs[evs.length - 1].time;
    const elapsed = t1 - t0;
    if (elapsed < 30) return null;
    const hasIncumbent = evs.some(e => e.event === 'incumbent');
    if (hasIncumbent) return null;
    return {
      kind: 'no_incumbent',
      severity: 'warning',
      elapsed,
      message: `可行解が未発見(経過${elapsed.toFixed(0)}s)。`,
    };
  }

  /**
   * high_gap_done: doneイベント受信時にgap>=50%(情報/グレー)。
   *
   * @param {object|null} summary - doneイベントのペイロード({gap, ...})。
   * @returns {{kind:string, severity:string, message:string, gap:number}|null}
   */
  function detectHighGapDone(summary) {
    if (!summary || summary.gap == null) return null;
    if (summary.gap < 0.5) return null;
    return {
      kind: 'high_gap_done',
      severity: 'info',
      gap: summary.gap,
      message: `大きなgap(${(summary.gap * 100).toFixed(1)}%)で終了。mk.analyze での診断を推奨。`,
    };
  }

  // --- ライブ指標 ---

  /**
   * TTFF (time-to-first-feasible): 最初のincumbentイベントのtime。
   *
   * @param {Array<object>} events
   * @returns {number|null}
   */
  function computeTTFF(events) {
    const first = (events || []).find(e => e.event === 'incumbent' && e.time != null);
    return first ? first.time : null;
  }

  /**
   * Primal Integral(区分定数積分)。 p(t) = |primal(t) - ref| / max(|primal(t)|, |ref|)。
   * イベント列の各区間 [t_i, t_{i+1}) で primal(t)=primal_i として台形でなく矩形近似する。
   *
   * @param {Array<object>} events - {time, primal} の列(時刻昇順を仮定)。
   * @param {number|null} ref - 基準primal値(ライブ中は現在のincumbent、確定値はdone後の最終primal)。
   * @returns {number} 積分値(refがnull、またはprimalイベントが無い場合は0)。
   */
  function primalIntegral(events, ref) {
    if (ref == null) return 0;
    const evs = (events || []).filter(e => e.primal != null && e.time != null)
      .slice().sort((a, b) => a.time - b.time);
    if (evs.length < 2) return 0;
    let total = 0;
    for (let i = 0; i < evs.length - 1; i++) {
      const dt = evs[i + 1].time - evs[i].time;
      if (dt <= 0) continue;
      const p = evs[i].primal;
      const denom = Math.max(Math.abs(p), Math.abs(ref)) || 1;
      const pt = Math.abs(p - ref) / denom;
      total += pt * dt;
    }
    return total;
  }

  const api = {
    detectLiveStall,
    detectNoIncumbent,
    detectHighGapDone,
    computeTTFF,
    primalIntegral,
  };

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api; // Node (tests/js/live_rules.test.js)
  } else {
    Object.assign(root, api); // ブラウザ: グローバルに関数を生やす
  }
})(typeof window !== 'undefined' ? window : globalThis);
