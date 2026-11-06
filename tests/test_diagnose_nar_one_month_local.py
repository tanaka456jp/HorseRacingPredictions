"""All local NAR staged-diagnostic fixtures are fictional, no real racing data."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
import csv
from io import StringIO
import json
from pathlib import Path
import sys

import pytest

from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from test_nar_local_monthly_intake import _make_zip
from test_nar_published_result_normalizer import _fixture


script = (Path(__file__).resolve().parents[1] /
          "scripts" / "diagnose_nar_one_month_local.py")
spec = spec_from_file_location("staged_nar_month_diagnostic", script)
assert spec is not None and spec.loader is not None
module = module_from_spec(spec)
spec.loader.exec_module(module)


def _report(path: Path):
    return module.diagnose_nar_month(
        path, expected_month="201711",
        personal_private_permission_confirmed=True,
    )


def test_offline_fictional_month_accepted_without_ev_or_licensed_row_export(tmp_path):
    source = _make_zip(tmp_path, month="201711")
    original = source.read_bytes()
    report = _report(source)
    assert report["status"] == "NAR_PRIVATE_MONTH_STRUCTURE_OK_PREOFF_UNVERIFIED"
    assert report["month"] == "201711"
    assert report["stage"] == "MONTH_COVERAGE"
    assert report["observedRaces"] == 1
    assert report["acceptedFlatRaces"] == 1
    assert report["acceptedFlatStarters"] == 8
    assert report["unresolvedInScopeRaces"] == 0
    assert report["completeMonth"]
    assert not report["sourceBytesUploaded"]
    assert not report["actualRightsIndependentlyVerified"]
    assert not report["preEventSnapshotVerified"]
    assert not report["modelTrainingExecuted"]
    assert not report["positiveEvDemonstrated"]
    assert source.read_bytes() == original
    assert str(source) not in json.dumps(report, ensure_ascii=False)
    assert "架空" not in json.dumps(report, ensure_ascii=False)


def test_bad_fictional_payback_yields_only_static_aggregate_reason(tmp_path):
    values = _fixture(month="201711")
    rows = list(csv.reader(StringIO(values["payback"])))
    rows[0][4] = "2"
    out = StringIO(newline="")
    csv.writer(out).writerows(rows)
    source = _make_zip(tmp_path, month="201711", override={"payback": out.getvalue()})
    report = _report(source)
    assert report["status"] == "NAR_PRIVATE_MONTH_REQUIRES_COVERAGE_REVIEW"
    assert report["stage"] == "MONTH_COVERAGE"
    assert report["observedRaces"] == 1
    assert report["unresolvedInScopeRaces"] == 1
    assert report["staticReasonCounts"] == {
        "NAR_PAYOUT_CONTRADICTS_FINAL_RESULTS": 1,
    }
    assert not report["positiveEvDemonstrated"]
    assert str(source) not in str(report)


def test_corrupt_fictional_zip_reports_static_stage_not_exception(tmp_path):
    source = tmp_path / "201711_1730041000_race.zip"
    source.write_bytes(b"not a ZIP")
    report = _report(source)
    assert report["status"] == "NAR_PRIVATE_MONTH_DIAGNOSTIC_BLOCKED"
    assert report["stage"] == "ZIP_METADATA"
    assert report["reasonCode"] == "NAR_ARCHIVE_UNREADABLE"
    assert str(source) not in str(report)


def test_operator_permission_and_holdout_month_checked_before_any_zip_read(tmp_path, monkeypatch):
    source = _make_zip(tmp_path, month="201711")
    def forbidden_inspect(*args, **kwargs):
        raise AssertionError("MUST NOT TOUCH SOURCE WITHOUT PERMISSION")
    monkeypatch.setattr(module, "inspect_nar_monthly_zip_structure", forbidden_inspect)
    with pytest.raises(UnsafeNarSource, match="NAR_PERSONAL_RESEARCH_PERMISSION_REQUIRED"):
        module.diagnose_nar_month(
            source, expected_month="201711",
            personal_private_permission_confirmed=False,
        )
    with pytest.raises(UnsafeNarSource, match="NAR_DIAGNOSTIC_TRAINING_MONTH_ONLY"):
        module.diagnose_nar_month(
            source, expected_month="202301",
            personal_private_permission_confirmed=True,
        )


def test_cli_prints_only_aggregate_for_fictional_source(tmp_path, monkeypatch, capsys):
    source = _make_zip(tmp_path, month="201711")
    monkeypatch.setattr(sys, "argv", [
        "diagnose_nar_one_month_local.py",
        "--local-monthly-race-zip", str(source),
        "--expected-month", "201711",
        "--confirm-personal-private-nar-permission",
    ])
    assert module.main() == 0
    stdout = capsys.readouterr().out
    report = json.loads(stdout)
    assert report["month"] == "201711"
    assert report["acceptedFlatRaces"] == 1
    assert str(source) not in stdout
    assert "架空馬" not in stdout
    assert not report["sourceBytesUploaded"]
