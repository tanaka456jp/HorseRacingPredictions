import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from horse_racing_predictions.exotic_longshot_phase11 import (
    center_residual_within_race,
)


def test_centering_is_race_relative_zero_sum_and_order_preserving():
    frame = pd.DataFrame(
        {"race_id": ["B", "A", "B", "A", "C"],
         "finish_position": [1, 2, 3, 4, 5]},
        index=[7, 2, 9, 4, 12],
    )
    raw = pd.Series([0.4, 0.3, 0.2, -0.1, 0.9], index=frame.index)
    centered = center_residual_within_race(frame, raw)
    np.testing.assert_allclose(
        centered.to_numpy(), [0.1, 0.2, -0.1, -0.2, 0.0],
    )
    assert centered.index.equals(frame.index)
    assert centered.groupby(frame["race_id"]).sum().abs().max() < 1e-12
    shifted = raw + frame["race_id"].map(
        {"A": 10.0, "B": -20.0, "C": 30.0}
    )
    np.testing.assert_allclose(
        center_residual_within_race(frame, shifted).to_numpy(),
        centered.to_numpy(),
    )
    changed = frame.copy()
    changed["finish_position"] = [9, 8, 7, 6, 5]
    pd.testing.assert_series_equal(
        center_residual_within_race(changed, raw), centered
    )


def test_centering_fails_closed_on_bad_inputs():
    frame = pd.DataFrame({"race_id": ["A", "A"]}, index=[3, 4])
    with pytest.raises(ValueError, match="index"):
        center_residual_within_race(frame, pd.Series([0.1, 0.2]))
    with pytest.raises(ValueError, match="non-finite"):
        center_residual_within_race(
            frame, pd.Series([0.1, np.inf], index=frame.index)
        )
    with pytest.raises(ValueError, match="race_id"):
        center_residual_within_race(
            frame.drop(columns="race_id"),
            pd.Series([0.1, 0.2], index=frame.index),
        )


def test_phase11_does_not_change_paper_or_final_holdout():
    source = Path(
        "src/horse_racing_predictions/exotic_longshot_phase11.py"
    ).read_text(encoding="utf-8")
    request = Path(
        "research/exotic_longshot_phase11_request.txt"
    ).read_text(encoding="utf-8")
    assert "oof_years=ROLLING_RESIDUAL_OOF_YEARS" in source
    assert '"final_holdout": "2025-2026 untouched"' in source
    assert '"forward_paper": "unchanged"' in source
    assert "2025-2026" in request
    assert "subtract within-race longshot residual mean" in source


def test_phase11_rejects_post_2024_history_before_model_training():
    from horse_racing_predictions.exotic_longshot_phase11 import (
        evaluate_longshot_race_centered_phase11,
    )
    sample = pd.DataFrame({
        "race_date": ["2024-12-31", "2025-01-01"],
        "race_id": ["A", "B"],
    })
    with pytest.raises(ValueError, match="post-2024"):
        evaluate_longshot_race_centered_phase11(sample)


def _phase11_path_guard():
    import importlib.util
    script = Path("scripts/evaluate_exotic_longshot_phase11.py").resolve()
    spec = importlib.util.spec_from_file_location("phase11_cli_guard", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.approved_development_history_path


def test_phase11_snapshot_guard_rejects_alias_and_missing_file(tmp_path):
    guard = _phase11_path_guard()
    approved = tmp_path / "data/research/development/free_history_through_2024.csv"
    manifest = approved.parent / "source_approval.json"
    approved.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "schema_version": 1,
        "approved_for_phase11": True,
        "source_type": "independent_free_pre2025_export",
        "contains_final_holdout": False,
        "source_name": "synthetic-fixture",
        "source_cutoff": "2024-12-31",
    }), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="Missing isolated"):
        guard("data/research/development/free_history_through_2024.csv", project_root=tmp_path)
    approved.parent.mkdir(parents=True)
    approved.write_text("race_date,race_id\\n2024-01-01,A\\n", encoding="utf-8")
    assert guard(approved, project_root=tmp_path) == approved
    with pytest.raises(ValueError, match="refuses general/full"):
        guard("data/jravan/full/current_history.csv", project_root=tmp_path)


def test_phase11_snapshot_guard_rejects_symlink(tmp_path):
    guard = _phase11_path_guard()
    approved = tmp_path / "data/research/development/free_history_through_2024.csv"
    approved.parent.mkdir(parents=True)
    target = tmp_path / "other.csv"
    target.write_text("sample", encoding="utf-8")
    try:
        approved.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError, match="symlinks/junctions"):
        guard(approved, project_root=tmp_path)
