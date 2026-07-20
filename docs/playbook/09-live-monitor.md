# 9. ライブ監視・run記録・再現(rerun)

[← プレイブック目次](index.md)

### こんな課題ありませんか

- 長時間の求解を「止まっているのか進んでいるのか」わからないまま待っている。
- 過去に試した設定を後から思い出せない(「あのときの実行はどのパラメータだった?」)。
- パラメータを何通りか試したいが、比較する仕組みがない。

### 診断で何がわかるか

ライブ監視自体は診断ルールとは独立(別レイヤー)。ただし単一run表示にはライブ簡易版の
症状バナー(`detectLiveStall`/`detectNoIncumbent`/`detectHighGapDone`)があり、これは
`collectors/attribution.detect_stalls` と同じ思想の JS 実装。「ライブ簡易判定。全診断は
`mk.analyze` で実施」と明記されており、`mk.analyze` の部分集合であることを隠していない。

### 打ち手の仕組み

TensorBoard型の「書き手/読み手分離」。書き手(`solve_with_monitor`)がソルバーのイベントを
`results/runs/<run_id>/` にファイルとして追記し、読み手(Flask+SSEサーバ)がそれを tail して
ブラウザへライブpushする。求解直前に SCIP パラメータ差分・モデルのfingerprint(変数/制約
内訳)・環境情報・git SHA を自動キャプチャして `meta.json` に残す(`capture=True` が既定)。
これにより「どの条件で解いた run か」が後から辿れる。アーキテクチャの全体像は
[利用マニュアル: ライブモニタ](../manual/live-monitor.md)の図を参照。

`mk.sweep` はパラメータ候補群を総当たりし、**各セットを普通の run として記録する**設計
なので、専用UIを作らずライブUIのrun比較(チェックボックス選択)がそのままスイープ結果比較
になる。`mk.rerun` は記録済み run の `scip_params_diff` を読み出して同じ条件で再求解する
(再現実行)。

### 効果(このリポジトリでの実測)

20秒求解で338 SSEフレームのライブ配信+done確定を確認。実データ検証では
`experiments/run_monitor.py --model plant --time 45` の実行(826イベント、gap 105.8%)に
対してライブ簡易stall判定が正しく発火(windowRate 0.514 < 0.5×overallRate 1.712)、
`detectHighGapDone` も gap 105.8%≥50%で発火する(task.md Phase 10-B)。

### 効かないとき・注意

- ライブの停滞バナーは「簡易判定」であり、全項目診断(`weak_relaxation` 等)は出ない。
  本格的な診断は `mk.analyze` を別途実行すること。
- `mk.rerun` は capture の無い run(`capture=False` で求解した旧run)には使えない
  (`ValueError`)。再現性を残したい run は capture をオプトアウトしないこと。

### 使い方

```powershell
# 読み手(開きっぱなし)
uv run python -m minlpkit.live.server   # http://127.0.0.1:5000

# 書き手(別ターミナル)
uv run python experiments/run_monitor.py --model plant --time 120 --gap 0.01
```

```python
import minlpkit as mk

param_sets = [{}, {"separating/maxroundsroot": 0}]
df = mk.sweep(build_model, param_sets, name="sched", time_limit=10)
new_run_id = mk.rerun(build_model, df["run_id"][0], time_limit=20)
```

API: [`mk.sweep`/`mk.rerun`/`solve_with_monitor`/`RunLogger`](../api/live.md)。
詳細は [利用マニュアル: ライブモニタ](../manual/live-monitor.md)。
