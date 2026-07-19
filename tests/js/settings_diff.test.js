// tests/js/settings_diff.test.js — buildSettingsDiff(live_rules.js) の純関数ユニットテスト
// 実行: node tests/js/settings_diff.test.js  (exit 0 で全パス)
'use strict';

const assert = require('assert');
const path = require('path');
const {buildSettingsDiff} = require(path.join(__dirname, '..', '..', 'minlpkit', 'live', 'live_rules.js'));

let nOK = 0;
function ok(name) { nOK++; console.log(`  ok - ${name}`); }

function rowByKey(rows, section, key) {
  return rows.find(r => r.section === section && r.key === key);
}

// --- (a) 2run、両方capture付き、scip_params_diffのキーが一部重複・一部固有 ---
(function () {
  const runs = [
    {
      label: 'plant (07-19 10:00)', color: '#2a78d6',
      meta: {
        params: {time_limit: 120, gap_limit: 0.01},
        capture: {
          scip_params_diff: {'limits/time': 120.0, 'separating/maxrounds': 1},
          fingerprint: {n_vars: 100, n_conss: 50, n_nonlinear: 5},
        },
      },
    },
    {
      label: 'plant (07-19 10:05)', color: '#008300',
      meta: {
        params: {time_limit: 120, gap_limit: 0.05},
        capture: {
          scip_params_diff: {'limits/time': 120.0, 'heuristics/emphasis': 'fast'},
          fingerprint: {n_vars: 100, n_conss: 50, n_nonlinear: 5},
        },
      },
    },
  ];
  const {columns, rows} = buildSettingsDiff(runs);
  assert.strictEqual(columns.length, 2);
  assert.ok(columns.every(c => c.hasCapture));

  // union of scip_params_diff keys, sorted
  const diffKeys = rows.filter(r => r.section === 'scip_params_diff').map(r => r.key);
  assert.deepStrictEqual(diffKeys, ['heuristics/emphasis', 'limits/time', 'separating/maxrounds']);

  // limits/time equal across both runs => not varies
  const rTime = rowByKey(rows, 'scip_params_diff', 'limits/time');
  assert.deepStrictEqual(rTime.values, [120.0, 120.0]);
  assert.strictEqual(rTime.varies, false, 'identical values across runs must not be flagged as varying');

  // separating/maxrounds only set in run0 => run1 gets null (means "default"), values differ => varies
  const rSep = rowByKey(rows, 'scip_params_diff', 'separating/maxrounds');
  assert.deepStrictEqual(rSep.values, [1, null]);
  assert.strictEqual(rSep.varies, true, 'set-in-one-run-only param must be flagged as varying');

  // gap_limit differs between runs (params section, independent of capture)
  const rGap = rowByKey(rows, 'params', 'gap_limit');
  assert.deepStrictEqual(rGap.values, [0.01, 0.05]);
  assert.strictEqual(rGap.varies, true);

  // time_limit identical
  const rTl = rowByKey(rows, 'params', 'time_limit');
  assert.strictEqual(rTl.varies, false);

  // fingerprint identical across both => not varies
  const rNVars = rowByKey(rows, 'fingerprint', 'n_vars');
  assert.strictEqual(rNVars.varies, false);

  ok('buildSettingsDiff: union of scip_params_diff keys + varies flag for differing/identical rows');
})();

// --- (b) captureなしの旧runが混在する場合 ---
(function () {
  const runs = [
    {
      label: 'plant (new)', color: '#2a78d6',
      meta: {
        params: {time_limit: 60, gap_limit: 0.01},
        capture: {scip_params_diff: {'limits/time': 60.0}, fingerprint: {n_vars: 10, n_conss: 5, n_nonlinear: 1}},
      },
    },
    {
      label: 'sched (old, no capture)', color: '#008300',
      meta: {params: {time_limit: 60, gap_limit: 0.01}},  // capture欠落(旧run)
    },
  ];
  const {columns, rows} = buildSettingsDiff(runs);
  assert.strictEqual(columns[0].hasCapture, true);
  assert.strictEqual(columns[1].hasCapture, false, 'old run without capture must be flagged hasCapture=false');

  // fingerprint/scip_params_diff行は旧runの列がundefined(「記録なし」表示用)
  const rNVars = rowByKey(rows, 'fingerprint', 'n_vars');
  assert.strictEqual(rNVars.values[0], 10);
  assert.strictEqual(rNVars.values[1], undefined, 'no-capture column must be undefined for fingerprint rows');
  // 片方しか値が無いので比較不能 = varies は false(誤って強調しない)
  assert.strictEqual(rNVars.varies, false, 'a single present value must not be flagged as varying');

  // params行(time_limit/gap_limit)はcaptureが無くても両方値がある
  const rTl = rowByKey(rows, 'params', 'time_limit');
  assert.deepStrictEqual(rTl.values, [60, 60]);
  assert.strictEqual(rTl.varies, false);

  ok('buildSettingsDiff: capture-less run yields undefined for capture-derived rows, params rows unaffected');
})();

// --- (c) capture自体はあるがscip_params_diffが空({})の場合、行はゼロになりうる ---
(function () {
  const runs = [
    {label: 'a', color: '#111', meta: {params: {}, capture: {scip_params_diff: {}, fingerprint: {n_vars: 1, n_conss: 1, n_nonlinear: 0}}}},
    {label: 'b', color: '#222', meta: {params: {}, capture: {scip_params_diff: {}, fingerprint: {n_vars: 1, n_conss: 1, n_nonlinear: 0}}}},
  ];
  const {rows} = buildSettingsDiff(runs);
  const diffRows = rows.filter(r => r.section === 'scip_params_diff');
  assert.strictEqual(diffRows.length, 0, 'no scip_params_diff keys across all runs => zero rows in that section');
  ok('buildSettingsDiff: empty scip_params_diff across all runs => no rows in that section');
})();

console.log(`\n${nOK} assertions passed`);
process.exit(0);
