// tests/js/live_rules.test.js — live_rules.js の純関数ユニットテスト(素のassert、テストランナー不要)
// 実行: node tests/js/live_rules.test.js  (exit 0 で全パス)
'use strict';

const assert = require('assert');
const path = require('path');
const {
  detectLiveStall,
  detectNoIncumbent,
  detectHighGapDone,
  computeTTFF,
  primalIntegral,
} = require(path.join(__dirname, '..', '..', 'minlpkit', 'live', 'live_rules.js'));

let nOK = 0;
function ok(name) { nOK++; console.log(`  ok - ${name}`); }

// --- (a) 序盤急改善→後半フラット+gap大 → stall検出 ---
(function () {
  const events = [
    { time: 0, dual: 0, gap: 1.0 },
    { time: 10, dual: 30 },
    { time: 20, dual: 60 },
    { time: 30, dual: 90 },
    { time: 40, dual: 90.5 },
    { time: 50, dual: 91 },
    { time: 60, dual: 91.3 },
    { time: 70, dual: 91.5 },
    { time: 80, dual: 91.7 },
    { time: 90, dual: 91.85 },
    { time: 100, dual: 92, gap: 0.5 },
  ];
  const r = detectLiveStall(events, 100);
  assert.ok(r, 'stall should be detected for early-fast/late-flat trajectory with large gap');
  assert.strictEqual(r.kind, 'dual_stall');
  assert.ok(r.windowRate < 0.5 * r.overallRate, 'window rate must be below 50% of overall rate');
  ok('detectLiveStall: early-burst then flat + high gap => stall');
})();

// --- (b) 一定レートで改善継続 → 非検出 ---
(function () {
  const events = [];
  for (let t = 0; t <= 100; t += 10) {
    events.push({ time: t, dual: 0.9 * t, gap: t === 100 ? 0.4 : 0.8 });
  }
  const r = detectLiveStall(events, 100);
  assert.strictEqual(r, null, 'steady-rate improvement must not be flagged as stall');
  ok('detectLiveStall: steady-rate improvement => no stall');
})();

// gapが十分小さい場合は停滞していても発火しない(gap>=5%条件)
(function () {
  const events = [
    { time: 0, dual: 0, gap: 0.5 },
    { time: 10, dual: 30 },
    { time: 20, dual: 60 },
    { time: 30, dual: 90 },
    { time: 40, dual: 90.5 },
    { time: 100, dual: 92, gap: 0.02 },
  ];
  const r = detectLiveStall(events, 100);
  assert.strictEqual(r, null, 'low current gap must suppress the stall banner');
  ok('detectLiveStall: low gap suppresses stall even if rate dropped');
})();

// --- (c) incumbentなし30秒 → no_incumbent ---
(function () {
  const events = [];
  for (let t = 0; t <= 35; t += 5) events.push({ time: t, event: 'node' });
  const r = detectNoIncumbent(events, 35);
  assert.ok(r, 'no_incumbent should fire after 30s with zero incumbent events');
  assert.strictEqual(r.kind, 'no_incumbent');
  ok('detectNoIncumbent: 30s elapsed, zero incumbents => fires');
})();

(function () {
  const events = [
    { time: 0, event: 'node' },
    { time: 12, event: 'incumbent', primal: 100 },
    { time: 35, event: 'node' },
  ];
  const r = detectNoIncumbent(events, 35);
  assert.strictEqual(r, null, 'an incumbent event within the window must suppress no_incumbent');
  ok('detectNoIncumbent: incumbent present => no fire');
})();

(function () {
  const events = [{ time: 0, event: 'node' }, { time: 20, event: 'node' }];
  const r = detectNoIncumbent(events, 20);
  assert.strictEqual(r, null, 'must not fire before 30s elapsed');
  ok('detectNoIncumbent: <30s elapsed => no fire');
})();

// --- high_gap_done ---
(function () {
  assert.ok(detectHighGapDone({ gap: 0.6 }), 'gap>=50% at done must fire');
  assert.strictEqual(detectHighGapDone({ gap: 0.3 }), null, 'gap<50% at done must not fire');
  assert.strictEqual(detectHighGapDone(null), null, 'no summary must not fire');
  ok('detectHighGapDone: threshold at 50% behaves correctly');
})();

// --- TTFF ---
(function () {
  const events = [
    { time: 0, event: 'node' },
    { time: 12.5, event: 'incumbent', primal: 80 },
    { time: 20, event: 'incumbent', primal: 70 },
  ];
  assert.strictEqual(computeTTFF(events), 12.5);
  assert.strictEqual(computeTTFF([{ time: 5, event: 'node' }]), null);
  ok('computeTTFF: first incumbent time, or null when none');
})();

// --- (d) Primal Integralの手計算一致(簡単な階段列) ---
(function () {
  // p(t)=|100-50|/max(100,50)=0.5 held over dt=10 => integral=5
  const events = [{ time: 0, primal: 100 }, { time: 10, primal: 50 }];
  const v = primalIntegral(events, 50);
  assert.ok(Math.abs(v - 5) < 1e-9, `expected 5, got ${v}`);
  ok('primalIntegral: two-step staircase matches hand calculation (5.0)');
})();

(function () {
  // 3ステップ: [0,10) primal=100 ref=40 -> p=60/100=0.6 * 10 = 6
  //            [10,25) primal=60 ref=40 -> p=20/60=0.3333 * 15 = 5.0
  const events = [{ time: 0, primal: 100 }, { time: 10, primal: 60 }, { time: 25, primal: 60 }];
  const v = primalIntegral(events, 40);
  const expected = 6 + 5.0;
  assert.ok(Math.abs(v - expected) < 1e-6, `expected ${expected}, got ${v}`);
  ok('primalIntegral: three-step staircase matches hand calculation');
})();

(function () {
  assert.strictEqual(primalIntegral([], 10), 0);
  assert.strictEqual(primalIntegral([{ time: 0, primal: 5 }], null), 0);
  ok('primalIntegral: degenerate inputs return 0');
})();

console.log(`\n${nOK} assertions passed`);
process.exit(0);
