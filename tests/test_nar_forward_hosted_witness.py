"""Fictional GitHub-hosted witness checks. No private data or betting."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import importlib.util
from pathlib import Path

import pytest

from horse_racing_predictions.nar_forward_hosted_witness import (
    validate_nar_github_hosted_receipt,
)

# Repo scripts are intentionally NOT packaged in the installable library.
# Load the exact reviewed CLI path rather than relying on tests/ being able
# to import a top-level 'scripts' namespace on all CI/Python entrypoints.
_PATH = Path(__file__).resolve().parents[1] / "scripts" / "anchor_nar_gh_hosted_receipt.py"
_SPEC = importlib.util.spec_from_file_location("nar_forward_receipt_cli_fixture", _PATH)
assert _SPEC is not None and _SPEC.loader is not None
receipt_cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(receipt_cli)
create_hosted_receipt_from_event = receipt_cli.create_hosted_receipt_from_event
main = receipt_cli.main

OFF = datetime(2026, 11, 14, 6, 0, tzinfo=timezone.utc)
NOW = OFF - timedelta(days=1)
DIGEST = "a" * 64
INPUTS = {
    "commitment_digest": DIGEST,
    "earliest_off_utc": "2026-11-14T06:00:00Z",
    "race_day_jst": "2026-11-14",
    "registered_flat_races": "36",
    "fictional_demo": "true",
}
ENV = {
    "GITHUB_ACTIONS": "true",
    "GITHUB_SERVER_URL": "https://github.com",
    "EXPECTED_RUNNER_ENVIRONMENT": "github-hosted",
    "GITHUB_REPOSITORY": "tanaka456jp/HorseRacingPredictions",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_RUN_ID": "12345678910",
    "GITHUB_RUN_ATTEMPT": "1",
}


def _run(inputs=None, env=None, when=NOW):
    ctx = dict(ENV)
    if env:
        ctx.update(env)
    return validate_nar_github_hosted_receipt(
        inputs=INPUTS if inputs is None else inputs,
        repository=ctx["GITHUB_REPOSITORY"], ref=ctx["GITHUB_REF"],
        event_name=ctx["GITHUB_EVENT_NAME"],
        run_id=ctx["GITHUB_RUN_ID"],
        run_attempt=ctx["GITHUB_RUN_ATTEMPT"],
        observed_utc=when,
    )


def test_structural_window_never_reports_independent_timestamp_or_ev():
    a = _run()
    assert a.schema == "NAR.GitHubHostedDigestReceipt.v1"
    assert a.status == "FICTIONAL_HOSTED_RECEIPT_NO_REAL_FORECAST"
    assert a.github_run_id == 12345678910
    assert a.run_url == (
        "https://github.com/tanaka456jp/HorseRacingPredictions/actions/runs/12345678910"
    )
    assert a.declared_flat_races == 36
    assert a.within_host_clock_lead_window
    assert not a.github_created_at_independently_verified
    assert not a.github_dispatch_input_independently_verified
    assert not a.private_snapshot_independently_verified
    assert not a.independently_attested_before_off
    assert not a.official_schedule_independently_verified
    assert not a.source_rights_verified
    assert not a.real_wagers_verified
    assert not a.positive_expected_value_demonstrated
    assert DIGEST not in repr(a)


def test_public_receipt_envelope_contains_digest_but_no_private_runners():
    doc = create_hosted_receipt_from_event(
        {"inputs": INPUTS, "untrusted_race_name": "PRIVATE_HORSE"},
        ENV, NOW,
    )
    assert doc["digestSha256"] == DIGEST
    assert doc["registeredFlatRaces"] == 36
    assert doc["hostLoggedAtUtc"] == "2026-11-13T06:00:00Z"
    assert not doc["githubRunCreatedAtIndependentlyVerified"]
    assert not doc["privateForecastSnapshotIndependentlyVerified"]
    assert not doc["positiveExpectedValueDemonstrated"]
    assert "PRIVATE_HORSE" not in json.dumps(doc)
    assert "first_off" not in doc


def test_prospective_mode_still_never_self_verifies_external_proof():
    inp = {**INPUTS, "fictional_demo": "false"}
    a = _run(inputs=inp)
    assert a.status == "PROSPECTIVE_DIGEST_RECEIVED_EXTERNAL_PROOF_PENDING"
    assert not a.fictional_demo
    assert not a.independently_attested_before_off
    assert not a.positive_expected_value_demonstrated


@pytest.mark.parametrize(("change", "reason"), [
    ({"GITHUB_REF": "refs/heads/feature/weekly-odds-free-note-20261021"},
     "NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT"),
    ({"GITHUB_EVENT_NAME": "push"}, "NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT"),
    ({"GITHUB_REPOSITORY": "someone/Fork"}, "NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT"),
    ({"GITHUB_RUN_ATTEMPT": "2"}, "NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT"),
    ({"GITHUB_RUN_ID": "0"}, "NAR_GH_RECEIPT_UNTRUSTED_RUN_CONTEXT"),
])
def test_dispatch_only_main_exact_repo_first_run(change, reason):
    with pytest.raises(ValueError, match=reason):
        _run(env=change)


@pytest.mark.parametrize(("change", "reason"), [
    ({"commitment_digest": "invalid"}, "NAR_GH_RECEIPT_INVALID_DIGEST"),
    ({"commitment_digest": "F" * 64}, "NAR_GH_RECEIPT_INVALID_DIGEST"),
    ({"earliest_off_utc": "2026-11-14T06:00:00+00:00"},
     "NAR_GH_RECEIPT_OFF_UTC_CANONICAL_REQUIRED"),
    ({"earliest_off_utc": "2026-11-14T26:00:00Z"},
     "NAR_GH_RECEIPT_OFF_UTC_INVALID"),
    ({"race_day_jst": "2026-11-13"},
     "NAR_GH_RECEIPT_RACE_DAY_OR_OFF_MISMATCH"),
    ({"race_day_jst": "2024-10-26"},
     "NAR_GH_RECEIPT_RACE_DAY_OR_OFF_MISMATCH"),
    ({"registered_flat_races": "0"},
     "NAR_GH_RECEIPT_RACE_COUNT_INVALID"),
    ({"registered_flat_races": "401"},
     "NAR_GH_RECEIPT_RACE_COUNT_INVALID"),
    ({"registered_flat_races": "036"},
     "NAR_GH_RECEIPT_RACE_COUNT_INVALID"),
    ({"fictional_demo": "yes"}, "NAR_GH_RECEIPT_DEMO_MODE_INVALID"),
])
def test_receipt_rejects_tainted_input_before_public_log(change, reason):
    with pytest.raises(ValueError, match=reason):
        _run(inputs={**INPUTS, **change})


@pytest.mark.parametrize("when", [
    OFF,
    OFF - timedelta(minutes=4),
    OFF - timedelta(minutes=5),
    OFF - timedelta(days=8),
])
def test_late_or_excessively_early_host_clock_never_pretends_preoff(when):
    with pytest.raises(ValueError, match="NAR_GH_RECEIPT_NOT_IN_PREOFF_HOST_WINDOW"):
        _run(when=when)


def test_untrusted_runner_environment_rejected_before_echoing_digest():
    with pytest.raises(ValueError, match="NAR_GH_RECEIPT_NOT_GITHUB_HOSTED"):
        create_hosted_receipt_from_event(
            {"inputs": INPUTS},
            {**ENV, "EXPECTED_RUNNER_ENVIRONMENT": "self-hosted"}, NOW,
        )
    with pytest.raises(ValueError, match="NAR_GH_RECEIPT_NOT_GITHUB_HOSTED"):
        create_hosted_receipt_from_event(
            {"inputs": INPUTS},
            {**ENV, "GITHUB_SERVER_URL": "https://github.invalid"}, NOW,
        )


def test_main_accepts_github_event_fixture_no_raw_content_echo(tmp_path, monkeypatch, capsys):
    event = tmp_path / "dispatch.json"
    event.write_text(json.dumps({"inputs": INPUTS}), encoding="utf-8")
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    monkeypatch.setattr(receipt_cli, "create_hosted_receipt_from_event",
        lambda data, env, now: create_hosted_receipt_from_event(data, env, NOW))
    assert main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["digestSha256"] == DIGEST
    assert not out["githubRunCreatedAtIndependentlyVerified"]
    assert not out["privateRaceHorseDataTransferred"]


def test_main_blocks_invalid_json_without_echoing_path_or_source(tmp_path, monkeypatch, capsys):
    event = tmp_path / "PRIVATE_RACE_DO_NOT_PRINT.json"
    event.write_text("{ invalid secret", encoding="utf-8")
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    assert main() == 2
    body = capsys.readouterr().out
    assert "PRIVATE_RACE" not in body
    assert "secret" not in body
    assert "NAR_GH_HOSTED_DIGEST_RECEIPT_HOLD" in body
