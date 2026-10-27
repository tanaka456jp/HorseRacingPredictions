"""Fake-data-only multi-shard conversion tests. No real JRA archive."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from horse_racing_predictions.pre2025_training_csv_audit import UnsafeTrainingSource
from horse_racing_predictions.pre2025_research_assembler import (
    stage_pre2025_ra_se_shards,
)
from test_jravan_parser import _ra, _se


def _old(text: str, *, race: int = 11, division: str | None = None):
    data = bytearray(text.encode("cp932"))
    data[11:15] = b"2024"
    data[15:19] = b"0926"
    data[25:27] = f"{race:02d}".encode("ascii")
    if division is not None:
        data[2:3] = division.encode("ascii")
    return data.decode("cp932")


def _write(path: Path, records):
    path.write_text(
        "\n".join(json.dumps({"record_type": kind, "text": text},
                             ensure_ascii=False) for kind, text in records) + "\n",
        encoding="utf8",
    )
    return path


def _fictional_sources(tmp_path):
    rows_ra = []
    rows_se = []
    for race in (11, 12):
        rows_ra.extend([
            ("RA", _old(_ra(data_division="3"), race=race)),
            ("RA", _old(_ra(data_division="7"), race=race)),
        ])
        for i in range(1, 5):
            rows_se.append((
                "SE",
                _old(_se(
                    i, f"架空{race}-{i}", i, 0 if i == 3 else 100 + i,
                    data_division="7", blood_no=f"202300{i:04d}",
                ), race=race),
            ))
    # Revise the same horse to incomplete at an earlier update division:
    # later race record must win and no duplicate horse appears.
    rows_se.insert(0, (
        "SE", _old(_se(
            1, "架空11-1", 0, 0, data_division="3",
            blood_no="",
        ), race=11),
    ))
    return [
        _write(tmp_path / "race_ra.jsonl", rows_ra),
        _write(tmp_path / "race_se.jsonl", rows_se),
    ]


def test_fictional_separate_ra_and_se_shards_become_year_partition(tmp_path):
    sources = _fictional_sources(tmp_path)
    destination = tmp_path / "new-private-research"
    result = stage_pre2025_ra_se_shards(sources, destination=destination)
    assert result.status == "PRIVATE_RESEARCH_STAGING_SOURCE_RIGHTS_PENDING"
    assert result.source_shards == 2
    assert result.saved_races == 2
    assert result.saved_runners == 8
    assert result.output_years == (2024,)
    assert result.model_training_started is False
    assert result.operator_rights_attested is False
    assert result.independently_verified_licence is False
    assert result.publication_authorized is False
    assert (destination / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING").exists()
    assert not (destination / "INCOMPLETE_DO_NOT_USE").exists()
    with (destination / "research_2024.csv").open(newline="", encoding="utf8") as f:
        values = list(csv.DictReader(f))
    assert len(values) == 8
    assert "win_odds" not in values[0]
    assert "popularity" not in values[0]
    assert len({(v["race_id"], v["horse_name"]) for v in values}) == 8
    assert all(v["race_date"] == "2024-09-26" for v in values)
    assert {v["finish_position"] for v in values} == {"1", "2", "3", "4"}
    receipt = json.loads(
        (destination / "private_research_manifest.json").read_text(encoding="utf8")
    )
    assert receipt["sourceRightsIndependentlyVerified"] is False
    assert receipt["trainWithoutSeparateSourceApproval"] is False
    assert receipt["protectedHoldoutTrainingAllowed"] is False
    assert receipt["publicationAuthorized"] is False
    assert "架空" not in (destination / "private_research_manifest.json").read_text()
    assert "架空" not in repr(result)


def test_rejects_2026_in_any_shard_before_new_dir_exists(tmp_path):
    sources = _fictional_sources(tmp_path)
    p = sources[1]
    with p.open("a", encoding="utf8") as f:
        f.write(json.dumps({
            "record_type": "SE",
            "text": _se(5, "保護ホールドアウト", 2, 340),
        }, ensure_ascii=False) + "\n")
    destination = tmp_path / "not-created"
    with pytest.raises(UnsafeTrainingSource, match="PROTECTED_HOLDOUT_IN_JSONL"):
        stage_pre2025_ra_se_shards(sources, destination=destination)
    assert not destination.exists()


def test_rejects_missing_se_source_before_creating_output(tmp_path):
    p = _write(tmp_path / "ra_only.jsonl", [
        ("RA", _old(_ra(), race=11)),
    ])
    out = tmp_path / "not-created"
    with pytest.raises(UnsafeTrainingSource, match="NO_MATCHABLE_RA_AND_SE"):
        stage_pre2025_ra_se_shards([p], destination=out)
    assert not out.exists()


def test_no_overwrite_even_with_preexisting_directory(tmp_path):
    sources = _fictional_sources(tmp_path)
    path = tmp_path / "existing"
    path.mkdir()
    (path / "important.txt").write_text("DONOTTOUCH", encoding="utf8")
    with pytest.raises(UnsafeTrainingSource, match="NEW_PRIVATE_OUTPUT_DIRECTORY_REQUIRED"):
        stage_pre2025_ra_se_shards(sources, destination=path)
    assert (path / "important.txt").read_text(encoding="utf8") == "DONOTTOUCH"


def test_incomplete_race_kept_out_of_yearly_training_partitions(tmp_path):
    sources = _fictional_sources(tmp_path)
    p = sources[1]
    lines = p.read_text(encoding="utf8").splitlines()
    # Remove all starters for race 12 except one; outcome must not be trained.
    cut = [
        line for line in lines
        if not ("架空12-" in line and not "架空12-1" in line)
    ]
    p.write_text("\n".join(cut) + "\n", encoding="utf8")
    out = tmp_path / "research"
    res = stage_pre2025_ra_se_shards(sources, destination=out)
    assert res.saved_races == 1
    assert res.saved_runners == 4
    assert res.excluded_incomplete_races == 1


def test_file_modified_after_first_full_audit_is_refused(tmp_path, monkeypatch):
    from horse_racing_predictions import pre2025_research_assembler as assembler

    sources = _fictional_sources(tmp_path)
    output = tmp_path / "snapshot-not-approved"
    original = assembler.audit_pre2025_ra_se_jsonl
    did_change = False

    def tamper_after_successful_full_audit(path):
        nonlocal did_change
        receipt = original(path)
        if not did_change:
            did_change = True
            content = path.read_text(encoding="utf-8")
            # A same-sized alteration is not detected by size; hash must
            # catch it during second pass before any success manifest.
            path.write_text(content.replace('"RA"', '"RB"', 1),
                            encoding="utf-8")
        return receipt

    monkeypatch.setattr(
        assembler, "audit_pre2025_ra_se_jsonl",
        tamper_after_successful_full_audit,
    )
    with pytest.raises(UnsafeTrainingSource, match="SOURCE_CHANGED_AFTER_FULL_AUDIT"):
        stage_pre2025_ra_se_shards(sources, destination=output)
    assert (output / "INCOMPLETE_DO_NOT_USE").exists()
    assert not (output / "private_research_manifest.json").exists()
    assert not (output / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING").exists()


def test_2025_row_mutated_after_full_audit_is_rejected_in_second_pass(
    tmp_path, monkeypatch,
):
    from horse_racing_predictions import pre2025_research_assembler as assembler

    sources = _fictional_sources(tmp_path)
    output = tmp_path / "snapshot"
    original = assembler.audit_pre2025_ra_se_jsonl
    did_change = False

    def insert_protected_after_audit(path):
        nonlocal did_change
        receipt = original(path)
        if not did_change:
            did_change = True
            content = path.read_text(encoding="utf-8")
            # Exactly same byte-length year replacement.
            path.write_text(content.replace("2024", "2026", 1),
                            encoding="utf-8")
        return receipt

    monkeypatch.setattr(
        assembler, "audit_pre2025_ra_se_jsonl",
        insert_protected_after_audit,
    )
    with pytest.raises(UnsafeTrainingSource):
        stage_pre2025_ra_se_shards(sources, destination=output)
    assert (output / "INCOMPLETE_DO_NOT_USE").exists()
    assert not (output / "private_research_manifest.json").exists()
