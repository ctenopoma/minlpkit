"""sweep / rerun の実SCIPテスト (Phase 10 C3)。

schedモデルを題材に、スイープ各メンバーが通常runとして記録されメタが正しいこと、
rerunが記録済みcaptureから同じパラメータで再現されることを確認する。
capture の無い(手作りの)偽runへのrerunがエラーになることも確認する。
"""
from __future__ import annotations

import json

import scheduling

from minlpkit.live import rerun, sweep

PARAM_SETS = [{}, {"separating/maxroundsroot": 0}]


def test_sweep_records_runs_with_sweep_meta(tmp_path):
    df = sweep(scheduling.build_model, PARAM_SETS, name="sched_test",
               time_limit=5, runs_root=tmp_path)

    assert len(df) == 2
    assert list(df["index"]) == [0, 1]

    for i, row in df.iterrows():
        run_dir = tmp_path / row["run_id"]
        assert run_dir.is_dir()
        meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8"))
        assert meta["sweep"]["name"] == "sched_test"
        assert meta["sweep"]["index"] == i
        assert meta["sweep"]["param_set"] == PARAM_SETS[i]
        assert (run_dir / "summary.json").exists()


def test_rerun_reproduces_captured_params(tmp_path):
    df = sweep(scheduling.build_model, [{"separating/maxroundsroot": 0}],
               name="sched_rerun_src", time_limit=5, runs_root=tmp_path)
    orig_run_id = df["run_id"][0]

    new_run_id = rerun(scheduling.build_model, orig_run_id, runs_root=tmp_path, time_limit=5)

    assert new_run_id != orig_run_id
    new_dir = tmp_path / new_run_id
    assert new_dir.is_dir()
    new_meta = json.loads((new_dir / "meta.json").read_text(encoding="utf-8"))
    assert new_meta["rerun_of"] == orig_run_id

    orig_meta = json.loads((tmp_path / orig_run_id / "meta.json").read_text(encoding="utf-8"))
    orig_diff = {k: v for k, v in orig_meta["capture"]["scip_params_diff"].items()
                 if not k.startswith("limits/")}
    new_diff = {k: v for k, v in new_meta["capture"]["scip_params_diff"].items()
                if not k.startswith("limits/")}
    # limits/* を除けば、rerunのcaptureは元のscip_params_diffを部分集合として含む
    for k, v in orig_diff.items():
        assert new_diff.get(k) == v


def test_rerun_without_capture_raises_clear_error(tmp_path):
    fake_run_id = "fake_run_no_capture"
    fake_dir = tmp_path / fake_run_id
    fake_dir.mkdir()
    (fake_dir / "meta.json").write_text(
        json.dumps({"run_id": fake_run_id, "model": "sched", "status": "done"}),
        encoding="utf-8")

    try:
        rerun(scheduling.build_model, fake_run_id, runs_root=tmp_path)
    except ValueError as e:
        assert "capture" in str(e)
    else:
        raise AssertionError("capture の無いrunへのrerunはValueErrorになるべき")


def test_rerun_missing_run_raises_file_not_found(tmp_path):
    try:
        rerun(scheduling.build_model, "does_not_exist", runs_root=tmp_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("存在しないrun_idへのrerunはFileNotFoundErrorになるべき")
