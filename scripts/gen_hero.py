"""Generate the README hero image: baseline vs exact linearization dual-bound trajectory."""

from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "samples"))

from minlpkit.live.monitor import solve_with_monitor
import scheduling_plant as sp

# Project palette (experiments/run_tree.py)
C = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e",
         muted="#898781", grid="#e1e0d9", axis="#c3c2b7")
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'
COL = {"base": "#d03b3b", "lin": "#2a78d6"}
LAB = {"base": "baseline (n·s bilinear)", "lin": "exact linearization"}
TLIM = 25.0


def main() -> None:
    traj = {}
    for key in ("base", "lin"):
        mon, s = solve_with_monitor(
            sp.build_model(linearize_ns=(key == "lin")),
            time_limit=TLIM, gap_limit=0.01)
        traj[key] = mon.to_frame()
        print(f"  {LAB[key]}: final_dual={s['dual']:.1f} gap={s['gap']*100:.1f}% nodes={s['nodes']}")

    fig = go.Figure()
    for key in ("base", "lin"):
        df = traj[key]
        fig.add_trace(go.Scatter(
            x=df["time"], y=df["dual"], mode="lines", name=LAB[key],
            line=dict(color=COL[key], width=2.5, shape="hv")))
    fig.update_layout(
        title=dict(text="Diagnose → reformulate → verify: exact linearization tightens the relaxation",
                   font=dict(color=C["ink"], size=17, family=FONT), x=0.02, y=0.94),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        font=dict(family=FONT, color=C["ink2"], size=13),
        xaxis=dict(title="solve time [s]", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        yaxis=dict(title="dual bound (higher = tighter)", gridcolor=C["grid"], linecolor=C["axis"],
                   tickfont=dict(color=C["muted"]), zeroline=False),
        margin=dict(l=70, r=28, t=64, b=52), width=1000, height=440,
        hovermode="x unified",
        legend=dict(orientation="h", y=0.02, yanchor="bottom", x=0.98, xanchor="right",
                    bgcolor="rgba(252,252,251,0.6)", font=dict(size=12, color=C["ink2"])))

    outdir = ROOT / "docs" / "assets"
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / "hero.png"
    fig.write_image(str(out), scale=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
