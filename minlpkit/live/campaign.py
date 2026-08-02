"""campaign — 軸を1つだけ変えた run 群の量産と横断診断(OpsOps 層)

3つの定型シナリオを「関連 run 群 + 変化軸」という1つの抽象に潰す:

- 入力シナリオ切替  → `scenario_sweep`(軸 = 入力インスタンス)
- パラメータ調整    → `minlpkit.live.sweep`(軸 = SCIP パラメータ。既存)
- 収束しない犯人探し → `ablate`(軸 = 制約グループの On/Off)

設計は sweep.py と同じ「各メンバーは**通常の run**」方式。各 run の
``meta.json`` に ``campaign``(``{"id", "kind", "axis"}``)を追記し、
campaign 全体の要約と **verdicts(ライブラリからの提案)** を
``<cwd>/results/campaigns/<campaign_id>/campaign.json`` に書く。
読み手(server.py の ``/campaigns``)はこのファイルと各 run の summary を
突き合わせてマトリクス表示する。OTel エクスポート(`minlpkit.otel`)も
同じ campaign.json を入力にする。
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from pyscipopt import Model

from .monitor import solve_with_monitor
from .run_logger import RUNS_ROOT, RunLogger
from .sweep import _unique_run_id

CAMPAIGNS_ROOT = RUNS_ROOT.parent / "campaigns"

# 「gap が残った」とみなすしきい値(5%)。ablate の verdict 判定に使う。
_STUCK_GAP = 0.05


def new_campaign_id(name: str, kind: str, root: Path | None = None) -> str:
    """`<name>_<kind>_<YYYYmmdd_HHMMSS>` 形式の一意な campaign_id を生成する。

    秒精度の衝突は既存ディレクトリを見て連番で回避する(sweep._unique_run_id と同方針)。

    Args:
        name: campaign 名(モデル識別子など)。
        kind: campaign 種別(``ablation`` / ``scenario`` / ``sweep``)。
        root: campaign ディレクトリの親。``None`` なら `CAMPAIGNS_ROOT`。

    Returns:
        campaign ディレクトリ名に使える文字列。
    """
    root = root if root is not None else CAMPAIGNS_ROOT
    base = f"{name}_{kind}_{datetime.now():%Y%m%d_%H%M%S}"
    candidate, suffix = base, 2
    while (root / candidate).exists():
        candidate = f"{base}_{suffix}"
        suffix += 1
    return candidate


def auto_groups(model: Model) -> dict[str, str]:
    """制約名の接頭辞から制約グループを自動抽出する(`ablate` の groups 省略時用)。

    制約名の括弧以降を落とし、さらに ``_`` 区切りの末尾セグメントのうち数字を含む
    もの(インデックス)を除いた文字列をグループ接頭辞とする
    (例: ``ramp_up_3`` → ``ramp_up``、``demand_J1`` → ``demand``、``cap[2,1]`` → ``cap``)。

    Args:
        model: グループを抽出する ``pyscipopt.Model``。

    Returns:
        ``{グループ名: 名前接頭辞}``。SCIP 既定の連番名(``c1``…)しか無いモデルでは
        1グループに潰れてしまうため、モデル構築時に意味のある制約名を付けておくこと。
    """
    groups: dict[str, str] = {}
    for c in model.getConss():
        parts = re.split(r"[\[\(]", c.name)[0].split("_")
        while len(parts) > 1 and re.search(r"\d", parts[-1]):
            parts.pop()
        prefix = "_".join(parts).rstrip("_") or c.name
        groups[prefix] = prefix
    return groups


def _matcher(spec: str | Callable[[str], bool]) -> Callable[[str], bool]:
    """グループ指定(名前接頭辞 or 述語)を制約名の述語に正規化する。"""
    if callable(spec):
        return spec
    return lambda name: name.startswith(spec)


def _run_member(model: Model, *, run_name: str, title: str, time_limit: float,
                campaign: dict, runs_root: Path) -> tuple[str, dict]:
    """campaign メンバー1件を通常の run として記録・求解する。"""
    model.hideOutput()
    run_id = _unique_run_id(run_name, runs_root)
    logger = RunLogger(
        run_id,
        meta=dict(model=run_name, title=title, params=dict(time_limit=time_limit)),
        root=runs_root,
    )
    _, summary = solve_with_monitor(model, time_limit=time_limit, logger=logger)
    logger.update_meta({"campaign": campaign})
    return run_id, summary


def _write_campaign_json(campaign_dir: Path, payload: dict) -> None:
    campaign_dir.mkdir(parents=True, exist_ok=True)
    (campaign_dir / "campaign.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _row(run_id: str, axis: dict, summary: dict) -> dict:
    return dict(
        run_id=run_id, axis=json.dumps(axis, ensure_ascii=False),
        status=str(summary["status"]), final_gap=summary["gap"],
        final_dual=summary["dual"], nodes=summary["nodes"], time=summary["time"],
    )


def _ablation_verdicts(baseline: dict, members: list[dict]) -> list[dict]:
    """baseline と各 Off-run の差分から「犯人制約グループ」への提案を作る。

    制約を外すことは緩和なので目的値の改善は当然起きる。そのため判定は
    status / gap / 時間の変化のみに基づく:

    - baseline が infeasible → Off で可解になった群は **実行不可能性に関与**(critical)
    - baseline の gap が残る → Off で gap がほぼ閉じた群は **収束ボトルネック**(serious)
    - baseline が最適 → Off で時間が 1/3 以下になった群は **求解時間の支配要因**(warning)
    """
    verdicts: list[dict] = []
    base_status = baseline["status"]
    base_gap = baseline.get("gap")
    base_time = baseline.get("time") or 0.0
    base_infeasible = base_status == "infeasible"
    base_stuck = (not base_infeasible) and base_gap is not None and base_gap >= _STUCK_GAP

    for mem in members:
        group = mem["axis"].get("off")
        if group is None:
            continue
        s, gap, t = mem["summary"]["status"], mem["summary"]["gap"], mem["summary"]["time"]
        if base_infeasible and s != "infeasible":
            verdicts.append(dict(
                group=group, severity="critical",
                verdict=f"制約グループ '{group}' が実行不可能性に関与(外すと {s})",
                evidence=f"baseline=infeasible → off('{group}')={s}",
                recipe="mk.diagnose_infeasibility(build_fn) で厳密な IIS 核(矛盾制約の極小集合)を特定し、"
                       "スラック上位の制約を緩和/RHS 見直し",
            ))
        elif base_stuck and gap is not None and gap <= max(0.01, base_gap * 0.2):
            verdicts.append(dict(
                group=group, severity="serious",
                verdict=f"制約グループ '{group}' が収束ボトルネック(外すと gap がほぼ閉じる)",
                evidence=f"gap {base_gap * 100:.1f}% → {gap * 100:.1f}% (off '{group}')",
                recipe="この群の緩和が弱い。mk.linearize_product / mk.pwl_sos2 による厳密線形化、"
                       "変数境界タイト化、Big-M の Indicator 化を検討(mk.compare_variants で効果検証)",
            ))
        elif (not base_infeasible and not base_stuck and base_time >= 1.0
              and s == base_status and t is not None and t <= base_time * (1 / 3)):
            verdicts.append(dict(
                group=group, severity="warning",
                verdict=f"制約グループ '{group}' が求解時間の支配要因",
                evidence=f"time {base_time:.1f}s → {t:.1f}s (off '{group}')",
                recipe="この群の定式化(カット・分枝への寄与)を見直す。mk.analyze で spatial_share / "
                       "停滞の帰属を確認",
            ))
    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3}
    verdicts.sort(key=lambda v: order.get(v["severity"], 9))
    return verdicts


def ablate(
    build_fn: Callable[[], Model],
    groups: dict[str, str | Callable[[str], bool]] | None = None,
    *,
    name: str = "ablate",
    time_limit: float = 20.0,
    runs_root: Path | None = None,
    campaigns_root: Path | None = None,
    otel_endpoint: str | None = None,
) -> pd.DataFrame:
    """制約グループを1つずつ Off にして求解し、「犯人」への提案を返す。

    「収束しない/実行不可能の原因を、制約を1個ずつ On/Off して探す」という
    手作業を campaign として自動化する。baseline(全制約 On)+ 各グループ Off の
    run を量産し、status / gap / 時間の変化から verdict(提案)を作る。

    Args:
        build_fn: 引数なしで新しい ``Model`` を返す callable(メンバーごとに呼ぶ)。
        groups: ``{グループ名: 制約名の接頭辞 or 述語(name -> bool)}``。``None`` なら
            `auto_groups` で制約名の接頭辞から自動抽出する。
        name: campaign / run_id の接頭辞。
        time_limit: 各メンバーの制限時間 [秒]。
        runs_root: run の書き出し先(既定 ``<cwd>/results/runs``)。
        campaigns_root: campaign.json の書き出し先(既定 ``<cwd>/results/campaigns``)。
        otel_endpoint: OTLP エンドポイント(例 ``http://localhost:4318``)。指定すると
            campaign 完了時に `minlpkit.otel.export_campaign` で trace/metrics/logs を送る
            (要 extras ``otel``)。

    Returns:
        pandas.DataFrame: 1メンバー1行。``run_id`` / ``axis`` / ``status`` /
        ``final_gap`` / ``final_dual`` / ``nodes`` / ``time`` / ``verdict``。
        先頭行が baseline(``axis`` の ``off`` が ``None``)。

    Example:
        ```python
        >>> import contextlib, io, tempfile
        >>> from pathlib import Path
        >>> from pyscipopt import Model
        >>> from minlpkit.live import ablate
        >>> def build():
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(lb=0, ub=10, name="x")
        ...     m.addCons(x >= 6, name="demand_min")
        ...     m.addCons(x <= 4, name="cap_max")   # demand と矛盾 → infeasible
        ...     m.setObjective(x, "minimize")
        ...     return m
        >>> with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        ...     df = ablate(build, {"demand": "demand", "cap": "cap"}, name="doctest_abl",
        ...                 time_limit=5, runs_root=Path(tmp) / "runs",
        ...                 campaigns_root=Path(tmp) / "campaigns")
        >>> df.iloc[0]["status"]        # baseline は矛盾で infeasible
        'infeasible'
        >>> (df["verdict"] != "").sum() >= 2   # どちらの群も「外すと可解」= 関与判定
        np.True_

        ```
    """
    runs_root = runs_root if runs_root is not None else RUNS_ROOT
    campaigns_root = campaigns_root if campaigns_root is not None else CAMPAIGNS_ROOT
    if groups is None:
        probe = build_fn()  # GC対策: ローカル変数に保持(FINDINGS §5)
        groups = dict(auto_groups(probe))
        del probe
    cid = new_campaign_id(name, "ablation", campaigns_root)

    members: list[dict] = []

    # baseline(全制約 On)
    m = build_fn()
    base_axis = {"off": None}
    run_id, summary = _run_member(
        m, run_name=name, title=f"{name} baseline", time_limit=time_limit,
        campaign={"id": cid, "kind": "ablation", "axis": base_axis}, runs_root=runs_root)
    baseline = {**summary, "status": str(summary["status"])}
    members.append(dict(run_id=run_id, axis=base_axis,
                        summary={**summary, "status": str(summary["status"])}))
    print(f"[baseline] {run_id}  status={baseline['status']}  gap={baseline['gap']}")

    # 各グループを Off
    for i, (gname, spec) in enumerate(groups.items()):
        match = _matcher(spec)
        m = build_fn()
        removed = [c for c in m.getConss() if match(c.name)]
        for c in removed:
            m.delCons(c)
        axis = {"off": gname, "n_removed": len(removed)}
        run_id, summary = _run_member(
            m, run_name=name, title=f"{name} off={gname}", time_limit=time_limit,
            campaign={"id": cid, "kind": "ablation", "axis": axis}, runs_root=runs_root)
        members.append(dict(run_id=run_id, axis=axis,
                            summary={**summary, "status": str(summary["status"])}))
        print(f"[{i + 1}/{len(groups)}] {run_id}  off={gname}(-{len(removed)}本)  "
              f"status={summary['status']}  gap={summary['gap']}")

    verdicts = _ablation_verdicts(baseline, members)
    payload = dict(
        campaign_id=cid, kind="ablation", name=name,
        created=datetime.now().isoformat(timespec="seconds"),
        baseline_run=members[0]["run_id"],
        members=[{"run_id": mem["run_id"], "axis": mem["axis"]} for mem in members],
        verdicts=verdicts,
    )
    _write_campaign_json(campaigns_root / cid, payload)

    rows = []
    vmap = {v["group"]: v["verdict"] for v in verdicts}
    for mem in members:
        r = _row(mem["run_id"], mem["axis"], mem["summary"])
        r["verdict"] = vmap.get(mem["axis"].get("off"), "")
        rows.append(r)
    df = pd.DataFrame(rows, columns=["run_id", "axis", "status", "final_gap",
                                     "final_dual", "nodes", "time", "verdict"])
    _maybe_export_otel(campaigns_root / cid, runs_root, otel_endpoint)
    return df


def scenario_sweep(
    build_fn: Callable[[Any], Model],
    instances: dict[str, Any],
    *,
    name: str = "scenario",
    time_limit: float = 20.0,
    runs_root: Path | None = None,
    campaigns_root: Path | None = None,
    otel_endpoint: str | None = None,
) -> pd.DataFrame:
    """入力インスタンス(シナリオ)を切り替えて同じモデルを量産求解する。

    「流すシナリオ(入力ファイル)を自動的に切り替えたい」用途の campaign。
    各インスタンスを軸 ``{"instance": ラベル}`` の run として記録し、
    infeasible なシナリオ(critical)・制限時間内に gap が閉じない難例(warning)へ
    verdict を付ける。

    Args:
        build_fn: インスタンス(入力データ/ファイルパス等)を1つ受け取り、新しい
            ``Model`` を返す callable。
        instances: ``{ラベル: インスタンス}``。ラベルは run の軸として記録される。
        name: campaign / run_id の接頭辞。
        time_limit: 各シナリオの制限時間 [秒]。
        runs_root: run の書き出し先(既定 ``<cwd>/results/runs``)。
        campaigns_root: campaign.json の書き出し先(既定 ``<cwd>/results/campaigns``)。
        otel_endpoint: OTLP エンドポイント。指定すると完了時に OTel エクスポート(要 extras)。

    Returns:
        pandas.DataFrame: 1シナリオ1行(列は `ablate` と同じ)。

    Example:
        ```python
        >>> import contextlib, io, tempfile
        >>> from pathlib import Path
        >>> from pyscipopt import Model
        >>> from minlpkit.live import scenario_sweep
        >>> def build(demand):
        ...     m = Model(); m.hideOutput()
        ...     x = m.addVar(lb=0, ub=5, name="x")
        ...     m.addCons(x >= demand, name="demand")
        ...     m.setObjective(x, "minimize")
        ...     return m
        >>> with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
        ...     df = scenario_sweep(build, {"low": 2, "over_cap": 9}, name="doctest_scn",
        ...                         time_limit=5, runs_root=Path(tmp) / "runs",
        ...                         campaigns_root=Path(tmp) / "campaigns")
        >>> list(df["status"])
        ['optimal', 'infeasible']

        ```
    """
    runs_root = runs_root if runs_root is not None else RUNS_ROOT
    campaigns_root = campaigns_root if campaigns_root is not None else CAMPAIGNS_ROOT
    cid = new_campaign_id(name, "scenario", campaigns_root)

    members: list[dict] = []
    for i, (label, inst) in enumerate(instances.items()):
        m = build_fn(inst)
        axis = {"instance": label}
        run_id, summary = _run_member(
            m, run_name=name, title=f"{name} instance={label}", time_limit=time_limit,
            campaign={"id": cid, "kind": "scenario", "axis": axis}, runs_root=runs_root)
        members.append(dict(run_id=run_id, axis=axis,
                            summary={**summary, "status": str(summary["status"])}))
        print(f"[{i + 1}/{len(instances)}] {run_id}  instance={label}  "
              f"status={summary['status']}  gap={summary['gap']}")

    verdicts: list[dict] = []
    for mem in members:
        label = mem["axis"]["instance"]
        s, gap = mem["summary"]["status"], mem["summary"]["gap"]
        if s == "infeasible":
            verdicts.append(dict(
                group=label, severity="critical",
                verdict=f"シナリオ '{label}' は実行不可能",
                evidence=f"instance('{label}')=infeasible",
                recipe="mk.diagnose_infeasibility(lambda: build_fn(instance)) で矛盾制約(IIS核)を特定",
            ))
        elif s != "optimal" and gap is not None and gap >= _STUCK_GAP:
            verdicts.append(dict(
                group=label, severity="warning",
                verdict=f"シナリオ '{label}' は難例(制限時間内に gap {gap * 100:.1f}% 残存)",
                evidence=f"instance('{label}'): status={s}, gap={gap * 100:.1f}%",
                recipe="難例だけ mk.analyze で個別診断、または ablate で犯人制約グループを特定",
            ))
    order = {"critical": 0, "serious": 1, "warning": 2, "good": 3}
    verdicts.sort(key=lambda v: order.get(v["severity"], 9))
    payload = dict(
        campaign_id=cid, kind="scenario", name=name,
        created=datetime.now().isoformat(timespec="seconds"),
        baseline_run=None,
        members=[{"run_id": mem["run_id"], "axis": mem["axis"]} for mem in members],
        verdicts=verdicts,
    )
    _write_campaign_json(campaigns_root / cid, payload)

    vmap = {v["group"]: v["verdict"] for v in verdicts}
    rows = []
    for mem in members:
        r = _row(mem["run_id"], mem["axis"], mem["summary"])
        r["verdict"] = vmap.get(mem["axis"]["instance"], "")
        rows.append(r)
    df = pd.DataFrame(rows, columns=["run_id", "axis", "status", "final_gap",
                                     "final_dual", "nodes", "time", "verdict"])
    _maybe_export_otel(campaigns_root / cid, runs_root, otel_endpoint)
    return df


def _maybe_export_otel(campaign_dir: Path, runs_root: Path, endpoint: str | None) -> None:
    """otel_endpoint 指定時に campaign を OTLP へ送る(extras 未導入は案内して続行)。"""
    if endpoint is None:
        return
    try:
        from ..otel import export_campaign
    except ModuleNotFoundError:
        print('OTel エクスポートには extras が必要です: uv add "minlpkit[otel]"')
        return
    try:
        export_campaign(campaign_dir, runs_root=runs_root, endpoint=endpoint)
        print(f"OTel export -> {endpoint} (campaign={campaign_dir.name})")
    except Exception as e:  # noqa: BLE001 - テレメトリ送信失敗で結果を失わない
        print(f"OTel export failed: {e}")
