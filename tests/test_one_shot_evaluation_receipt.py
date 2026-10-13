"""Synthetic one-shot receipt tests; never access JV-Link or real race data."""
from concurrent.futures import ThreadPoolExecutor
import json

import pytest

from horse_racing_predictions.one_shot_evaluation_receipt import (
    claim_one_shot,
    finalize_one_shot,
)

RACE_SHA = "a" * 64
PEDIGREE_SHA = "b" * 64
SUMMARY_SHA = "c" * 64


@pytest.mark.parametrize("phase", (12, 13))
def test_claim_precedes_finish_and_cannot_be_reset(tmp_path, phase):
    file = tmp_path / f"phase{phase}_evaluation_receipt.json"
    args = dict(
        phase=phase, race_archive_sha256=RACE_SHA,
        pedigree_snapshot_sha256=PEDIGREE_SHA if phase == 12 else None,
    )
    claim = claim_one_shot(file, **args)
    assert json.loads(file.read_text(encoding="utf-8")) == claim
    assert claim["status"] == f"phase{phase}_evaluation_started"
    assert claim["rerun_allowed"] is False
    assert claim["protected_holdout"] == "2025-2026 untouched"
    with pytest.raises(RuntimeError, match="must not be rerun"):
        claim_one_shot(file, **args)

    finalize_one_shot(file, claim=claim, summary_sha256=SUMMARY_SHA, passed=False)
    result = json.loads(file.read_text(encoding="utf-8"))
    assert result["status"] == f"phase{phase}_real_evaluation_consumed"
    assert result["summary_sha256"] == SUMMARY_SHA
    assert result["rerun_allowed"] is False
    with pytest.raises(RuntimeError, match="must not be rerun"):
        claim_one_shot(file, **args)
    with pytest.raises(RuntimeError, match="ownership"):
        finalize_one_shot(file, claim=claim, summary_sha256=SUMMARY_SHA, passed=True)


def test_atomic_parallel_claim_only_one_winner(tmp_path):
    receipt = tmp_path / "phase13_evaluation_receipt.json"

    def attempt(_):
        try:
            return claim_one_shot(
                receipt, phase=13, race_archive_sha256=RACE_SHA
            )["claim_id"]
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=12) as pool:
        claims = list(pool.map(attempt, range(24)))
    assert sum(item is not None for item in claims) == 1
    assert json.loads(receipt.read_text(encoding="utf-8"))["claim_id"] in claims


def test_claim_survives_crash_and_blocks_retry(tmp_path):
    receipt = tmp_path / "phase12_evaluation_receipt.json"
    claim_one_shot(
        receipt, phase=12, race_archive_sha256=RACE_SHA,
        pedigree_snapshot_sha256=PEDIGREE_SHA,
    )
    with pytest.raises(RuntimeError, match="must not be rerun"):
        claim_one_shot(
            receipt, phase=12, race_archive_sha256=RACE_SHA,
            pedigree_snapshot_sha256=PEDIGREE_SHA,
        )
    assert json.loads(receipt.read_text(encoding="utf-8"))["status"] == (
        "phase12_evaluation_started"
    )


def test_invalid_provenance_never_creates_a_receipt(tmp_path):
    receipt = tmp_path / "phase13_evaluation_receipt.json"
    with pytest.raises(ValueError, match="SHA-256"):
        claim_one_shot(
            receipt, phase=13, race_archive_sha256="bad"
        )
    assert not receipt.exists()


def test_existing_unparseable_receipt_still_blocks(tmp_path):
    receipt = tmp_path / "phase13_evaluation_receipt.json"
    receipt.write_text("corrupt", encoding="utf-8")
    with pytest.raises(RuntimeError, match="must not be rerun"):
        claim_one_shot(receipt, phase=13, race_archive_sha256=RACE_SHA)
    assert receipt.read_text(encoding="utf-8") == "corrupt"


def test_workflows_do_not_trigger_real_evaluations_from_synthetic_tests():
    from pathlib import Path

    for name in (
        "exotic-pedigree-phase12-self-hosted.yml",
        "exotic-conditional-partner-phase13-self-hosted.yml",
    ):
        text = (Path(".github/workflows") / name).read_text(encoding="utf-8")
        assert "workflow_dispatch" in text
        assert "research/exotic_" in text
        assert "runs-on: [self-hosted, Windows]" in text
