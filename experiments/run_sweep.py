"""SCIPパラメータスイープを実行し、parallel coordinates図で結果を比較する (Phase 10 C3)

各パラメータセットは通常の run として `results/runs/` に記録される(capture付き)。
これにより既存の runs一覧UI(`minlpkit.live.server`)がそのままスイープ結果比較UIになる。

実行例:
  uv run python experiments/run_sweep.py --model sched --time 6
  uv run python experiments/run_sweep.py --model plant --time 20 --config sweep.yaml

--config を省略すると組み込みのデモスイープ(separating/heuristics強度を変える4セット、
viz/tune.py で確認済みの「separating=fast系が固定時間の双対境界に効く」という知見を参考にした構成)を使う。

--config <yaml> は以下の形式:
  param_sets:
    - {}
    - separating/maxroundsroot: 0
    - heuristics/feaspump/freq: -1

出力: results/sweep.html (+ 目視確認用の results/_sweep.png)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent / "samples"))

from minlpkit.live import sweep

C = dict(surface="#fcfcfb", page="#f9f9f7", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9", axis="#c3c2b7")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'

MODELS = {
    "uc": ("unit_commitment", "プラント系 Unit Commitment"),
    "sched": ("scheduling", "バッチスケジューリング"),
    "plant": ("scheduling_plant", "バッチ反応器スケジューリング(プラント物理入り)"),
}

# デモスイープ: separating(分離)/heuristics(ヒューリスティクス)の強度を変える4セット。
# viz/tune.py の知見(固定時間ではseparating=fast寄りが双対境界を押す)を踏まえた構成:
#   #0 既定のまま(基準)
#   #1 ルート分離を弱める(fast寄り)
#   #2 ヒューリスティクスを弱める(fast寄り)
#   #3 両方を弱める(fast+fast相当)
DEMO_PARAM_SETS = [
    {},
    {"separating/maxroundsroot": 0},
    {"heuristics/feaspump/freq": -1, "heuristics/rens/freq": -1, "heuristics/rins/freq": -1},
    {"separating/maxroundsroot": 0,
     "heuristics/feaspump/freq": -1, "heuristics/rens/freq": -1, "heuristics/rins/freq": -1},
]


def _load_config(path: str) -> list[dict]:
    import yaml  # 環境に既存のPyYAMLを使う(コア依存には追加しない)

    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    param_sets = cfg.get("param_sets")
    if not param_sets:
        raise ValueError(f"{path} に 'param_sets' が見つかりません")
    return [dict(p) if p else {} for p in param_sets]


def fig_parcoords(df, param_sets: list[dict]) -> go.Figure:
    """パラメータ軸 + final_dual/final_gap 軸の parallel coordinates 図。"""
    param_names = sorted({k for p in param_sets for k in p})
    dims = []
    for name in param_names:
        vals = [float(p.get(name, 0.0)) for p in param_sets]
        dims.append(dict(label=name, values=vals,
                          tickvals=sorted(set(vals)),
                          range=[min(vals), max(vals)] if min(vals) != max(vals) else [min(vals) - 1, max(vals) + 1]))

    gaps = [g if g is not None else 1.0 for g in df["final_gap"]]
    duals = [d if d is not None else 0.0 for d in df["final_dual"]]
    dims.append(dict(label="final_dual", values=duals))
    dims.append(dict(label="final_gap", values=gaps))

    gmin, gmax = min(gaps), max(gaps)
    if gmin == gmax:  # 全セットが同じgap(=このモデルでは差が出なかった)でも色軸を退化させない
        gmin, gmax = gmin - 0.01, gmax + 0.01

    fig = go.Figure(data=go.Parcoords(
        line=dict(color=gaps, colorscale=[[0, "#0b2d5c"], [1, "#bcd6f5"]],
                  cmin=gmin, cmax=gmax,
                  showscale=True, colorbar=dict(title="final_gap", tickformat=".0%")),
        dimensions=dims,
        labelfont=dict(color=C["ink"], size=12, family=FONT),
        tickfont=dict(color=C["ink2"], size=10, family=FONT),
        rangefont=dict(color=C["muted"], size=10, family=FONT),
    ))
    fig.update_layout(
        title=dict(text="スイープ結果: パラメータ × final_dual / final_gap",
                   font=dict(color=C["ink"], size=15, family=FONT), x=0.01, y=0.98),
        paper_bgcolor=C["surface"], font=dict(family=FONT, color=C["ink2"], size=12),
        margin=dict(l=110, r=40, t=110, b=24), height=460,
    )
    return fig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=MODELS, default="plant")
    ap.add_argument("--time", type=float, default=20.0)
    ap.add_argument("--config", default=None, help="param_sets を定義するyamlファイル(省略時はデモ4セット)")
    args = ap.parse_args()

    module_name, title = MODELS[args.model]
    module = __import__(module_name)

    param_sets = _load_config(args.config) if args.config else DEMO_PARAM_SETS
    print(f"sweeping {module_name} ({len(param_sets)} sets, time_limit={args.time}s) ...")
    print(f"(ライブ表示: 別ターミナルで `uv run python -m minlpkit.live.server`)")

    df = sweep(module.build_model, param_sets, name=args.model, time_limit=args.time)

    print("\n結果:")
    print(df.to_string(index=False))

    outdir = Path(__file__).parent.parent / "results"
    outdir.mkdir(exist_ok=True)
    fig = fig_parcoords(df, param_sets)
    fig.write_image(str(outdir / "_sweep.png"), width=1000, height=420, scale=1)  # 目視確認用
    fig.write_html(str(outdir / "sweep.html"), include_plotlyjs=True, config=dict(displayModeBar=False))
    print(f"\nwrote {outdir / 'sweep.html'}")


if __name__ == "__main__":
    main()
