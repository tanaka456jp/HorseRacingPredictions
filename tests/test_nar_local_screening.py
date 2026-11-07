"""The only local ZIPs used here are fictional 72-month fixtures."""
from pathlib import Path
import zipfile

import pytest

from horse_racing_predictions.nar_local_screening import (
    screen_nar_local_2017_2022,
)
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_prior_day_features import _month
from test_nar_published_result_normalizer import _fixture


def _archive(tmp_path, month):
    source = tmp_path / f"{month}_1730041000_race.zip"
    rows = {**_month(month), "payback": _fixture(month=month)["payback"]}
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as zf:
        for kind, text in rows.items():
            zf.writestr(f"{month}_{kind}.csv", text.encode("cp932"))
    return source


def _all_72(tmp_path):
    return [
        _archive(tmp_path, f"{year}{month:02d}")
        for year in range(2017, 2023) for month in range(1, 13)
    ]


def test_only_exact_72_months_before_holdout_can_enter_screener(tmp_path):
    p = _archive(tmp_path, "201701")
    with pytest.raises(UnsafeNarSource, match="NAR_72_EXPLICIT_PERSONAL_SOURCES_REQUIRED"):
        screen_nar_local_2017_2022(
            [p], personal_private_permission_confirmed=True,
        )
    with pytest.raises(UnsafeNarSource, match="NAR_72_EXPLICIT_PERSONAL_SOURCES_REQUIRED"):
        screen_nar_local_2017_2022(
            [p] * 72, personal_private_permission_confirmed=True,
        )


def test_2023_holdout_not_even_opened_in_72_month_screener(tmp_path):
    paths = [
        tmp_path / f"{year}{month:02d}_1730041000_race.zip"
        for year in range(2017, 2023) for month in range(1, 13)
    ]
    paths[-1] = tmp_path / "202301_1730041000_race.zip"
    # No files are created; reject just from explicit names, before any I/O.
    with pytest.raises(UnsafeNarSource, match="NAR_TRAINING_MONTH_INVALID_OR_SEALED"):
        screen_nar_local_2017_2022(
            paths, personal_private_permission_confirmed=True,
        )


def test_no_unapproved_archive_is_opened(tmp_path):
    paths = [
        tmp_path / f"{year}{month:02d}_1730041000_race.zip"
        for year in range(2017, 2023) for month in range(1, 13)
    ]
    with pytest.raises(UnsafeNarSource, match="NAR_72_EXPLICIT_PERSONAL_SOURCES_REQUIRED"):
        screen_nar_local_2017_2022(
            paths, personal_private_permission_confirmed=False,
        )


def test_fictional_72_month_real_catboost_2022_tuning_only(tmp_path):
    pytest.importorskip("catboost")
    archives = _all_72(tmp_path)
    unchanged = [p.stat().st_size for p in archives]
    result = screen_nar_local_2017_2022(
        archives, personal_private_permission_confirmed=True, iterations=30,
    )
    m = result.metrics
    assert result.status == "NAR_PRIVATE_2022_SCREEN_ONLY_NO_LIVE_ROI"
    assert result.months_checked == 72
    assert result.races_checked == 72
    assert m.training_races == 60
    assert m.tuning_races == 12
    assert m.training_runners == 480
    assert m.tuning_runners == 96
    assert m.sealed_races_unscored == 0
    assert m.independent_models_fitted
    assert not m.sealed_holdout_labels_used
    assert not m.real_positive_expected_value_proven
    assert not m.official_returns_evaluated
    assert not m.public_distribution_authorized
    assert not result.real_economic_return_verified
    assert not result.independent_2023_2024_test_opened
    assert [p.stat().st_size for p in archives] == unchanged
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        p.name for p in archives
    )


def test_local_cli_is_network_free_and_prints_no_source_rows():
    content = Path("scripts/screen_nar_local_2017_2022.py").read_text(
        encoding="utf-8",
    )
    assert "--private-zip-paths-json" in content
    assert "--confirm-personal-private-nar-permission" in content
    assert "sourceRowsUploaded" in content
    assert "requests" not in content
    assert "urllib" not in content
    assert "sourceNames" not in content


def _load_local_cli():
    import importlib.util
    script = Path(__file__).resolve().parents[1] / "scripts" / "screen_nar_local_2017_2022.py"
    spec = importlib.util.spec_from_file_location("nar_local_screening_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_folder_cli_refuses_incomplete_months_without_reading_zip(tmp_path, monkeypatch, capsys):
    import json
    import sys
    _archive(tmp_path, "201701")
    cli = _load_local_cli()
    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("NO ZIP BYTES BEFORE 72 MONTH COVERAGE")
    monkeypatch.setattr(cli, "screen_nar_local_2017_2022", forbidden_read)
    monkeypatch.setattr(sys, "argv", [
        "screen_nar_local_2017_2022.py",
        "--local-nar-training-zip-directory", str(tmp_path),
        "--confirm-personal-private-nar-permission",
    ])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "NAR_LOCAL_SCREENING_BLOCKED_SOURCE_OR_FOLDS"
    assert not report["trainingExecuted"]
    assert not report["sourceRowsUploaded"]
    assert not report["sourceRightsIndependentlyVerified"]
    assert not report["independentHoldoutOpened"]


def test_folder_cli_2023_holdout_rejected_before_training(tmp_path, monkeypatch, capsys):
    import json
    import sys
    _archive(tmp_path, "202301")
    cli = _load_local_cli()
    def forbidden_read(*_args, **_kwargs):
        raise AssertionError("SEALED MONTH MUST NOT BE OPENED")
    monkeypatch.setattr(cli, "screen_nar_local_2017_2022", forbidden_read)
    monkeypatch.setattr(sys, "argv", [
        "screen_nar_local_2017_2022.py",
        "--local-nar-training-zip-directory", str(tmp_path),
        "--confirm-personal-private-nar-permission",
    ])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "NAR_LOCAL_SCREENING_BLOCKED_SOURCE_OR_FOLDS"
    assert not report["independentHoldoutOpened"]
    assert not report["trainingExecuted"]


def test_folder_cli_requires_permission_before_any_private_inventory(tmp_path, monkeypatch, capsys):
    import json
    import sys
    cli = _load_local_cli()
    def forbidden_inventory(*_args, **_kwargs):
        raise AssertionError("NO INVENTORY WITHOUT PERMISSION")
    monkeypatch.setattr(cli, "inventory_private_nar_training_directory",
                        forbidden_inventory)
    monkeypatch.setattr(sys, "argv", [
        "screen_nar_local_2017_2022.py",
        "--local-nar-training-zip-directory", str(tmp_path),
    ])
    assert cli.main() == 2
    report = json.loads(capsys.readouterr().out)
    assert not report["trainingExecuted"]
    assert not report["sourceRowsUploaded"]


def test_folder_cli_72_fictional_months_fit_both_catboost_models(tmp_path, monkeypatch, capsys):
    import json
    import sys
    pytest.importorskip("catboost")
    paths = _all_72(tmp_path)
    originals = [p.stat().st_size for p in paths]
    cli = _load_local_cli()
    monkeypatch.setattr(sys, "argv", [
        "screen_nar_local_2017_2022.py",
        "--local-nar-training-zip-directory", str(tmp_path),
        "--confirm-personal-private-nar-permission",
        "--iterations", "30",
    ])
    assert cli.main() == 0
    stdout = capsys.readouterr().out
    report = json.loads(stdout)
    assert report["monthsChecked"] == 72
    assert report["trainingRaces"] == 60
    assert report["tuningRaces"] == 12
    assert report["modelTrainingExecutedLocally"]
    assert not report["realPayoutRoiVerified"]
    assert not report["positiveExpectedValueDemonstrated"]
    assert not report["modelBinarySaved"]
    assert not report["sourceRowsUploaded"]
    assert not report["sourceRightsIndependentlyVerified"]
    assert not report["contemporaneousPreoffSnapshotVerified"]
    assert not report["independentHoldoutOpened"]
    assert "架空馬" not in stdout and "架空競馬場" not in stdout
    assert str(tmp_path) not in stdout
    assert [p.stat().st_size for p in paths] == originals
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(p.name for p in paths)


def test_legacy_private_json_path_list_is_preserved(tmp_path, monkeypatch, capsys):
    import json
    import sys
    cli = _load_local_cli()
    archive = _archive(tmp_path, "201701")
    manifest = tmp_path / "private.json"
    manifest.write_text(json.dumps([str(archive)] * 72), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "screen_nar_local_2017_2022.py",
        "--private-zip-paths-json", str(manifest),
        "--confirm-personal-private-nar-permission",
    ])
    assert cli.main() == 2
    assert json.loads(capsys.readouterr().out)["status"] == (
        "NAR_LOCAL_SCREENING_BLOCKED_SOURCE_OR_FOLDS"
    )
