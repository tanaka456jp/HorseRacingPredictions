import hashlib
import json

from horse_racing_predictions.jravan_archive_reassessment import (
    reassess_local_archive_manifest,
)
from horse_racing_predictions.jravan_free_trial_archive import (
    DEFAULT_ARCHIVE_RANGE,
)


def _manifest():
    return {
        "status": "partial",
        "created_at_utc": "2026-10-11T10:36:29+00:00",
        "jvopen_range": DEFAULT_ARCHIVE_RANGE,
        "option": 4,
        "dataspecs": ["RACE", "BLDN", "SLOP", "HOSN"],
        "excluded_dataspecs": ["TOKU", "YSCH"],
        "protected_holdout": "2025-2026 not used for modeling/evaluation",
        "raw_redistribution_allowed": False,
        "parts": [
            {
                "dataspec": "RACE",
                "status": "failed",
                "records_written": 0,
                "record_type_counts": {},
                "output_sha256": None,
                "output_path": "missing-race.jsonl",
                "read_count": None,
                "download_count": None,
                "last_file_timestamp": None,
                "error": "JraVanApiError: JVOpen failed with return code -301 for dataspec=RACE",
            },
            {
                "dataspec": "BLDN",
                "status": "success",
                "records_written": 79888,
                "record_type_counts": {"HN": 16896, "SK": 62992},
                "output_sha256": "a" * 64,
                "output_path": "missing-bldn.jsonl",
                "read_count": 192,
                "download_count": 192,
                "last_file_timestamp": "20241229143624",
                "error": None,
            },
            {
                "dataspec": "SLOP",
                "status": "success",
                "records_written": 3740223,
                "record_type_counts": {"HC": 3740223},
                "output_sha256": "b" * 64,
                "output_path": "missing-slop.jsonl",
                "read_count": 96,
                "download_count": 96,
                "last_file_timestamp": "20250103203141",
                "error": None,
            },
            {
                "dataspec": "HOSN",
                "status": "failed",
                "records_written": 0,
                "record_type_counts": {},
                "output_sha256": None,
                "output_path": "missing-hosn.jsonl",
                "read_count": None,
                "download_count": None,
                "last_file_timestamp": None,
                "error": "JraVanApiError: JVOpen failed with return code -1 for dataspec=HOSN",
            },
        ],
        "total_records_written": 3820111,
    }


def test_reassessment_preserves_original_and_writes_v2_without_raw_reads(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    source = root / "latest_manifest.json"
    original = json.dumps(_manifest(), ensure_ascii=False, indent=2).encode("utf-8")
    source.write_bytes(original)

    report = tmp_path / "report.json"
    reassessed, summary = reassess_local_archive_manifest(
        root,
        report_path=report,
    )

    assert source.read_bytes() == original
    assert (root / "latest_manifest_v2.json").is_file()
    assert reassessed["manifest_version"] == 2
    assert reassessed["status"] == "partial"

    parts = {
        part["dataspec"]: part
        for part in reassessed["parts"]
    }
    assert parts["RACE"]["status"] == "failed"
    assert parts["RACE"]["research_use_allowed"] is False

    assert parts["BLDN"]["status"] == "success"
    assert parts["BLDN"]["research_use_allowed"] is True
    assert parts["BLDN"]["quarantine_reason"] is None

    assert parts["SLOP"]["status"] == "success"
    assert parts["SLOP"]["research_use_allowed"] is False
    assert "not certifiably pre-2025" in parts["SLOP"]["quarantine_reason"]

    assert parts["HOSN"]["status"] == "no_data"
    assert parts["HOSN"]["error"] is None
    assert "return code -1" in parts["HOSN"]["original_error"]

    assert summary.research_approved_dataspecs == ("BLDN",)
    assert summary.quarantined_dataspecs == ("SLOP",)
    assert summary.no_data_dataspecs == ("HOSN",)
    assert summary.failed_dataspecs == ("RACE",)
    assert len(summary.original_manifest_sha256) == 64
    assert len(summary.reassessed_manifest_sha256) == 64
    assert summary.original_manifest_sha256 == hashlib.sha256(original).hexdigest()

    report_payload = json.loads(report.read_text(encoding="utf-8"))
    assert report_payload["raw_records_read_during_reassessment"] is False
    assert report_payload["research_approved_dataspecs"] == ["BLDN"]
    assert report_payload["quarantined_dataspecs"] == ["SLOP"]


def test_reassessment_fails_closed_on_wrong_provider_range(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    payload = _manifest()
    payload["jvopen_range"] = "20170101000000-20250101000000"
    (root / "latest_manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )

    try:
        reassess_local_archive_manifest(root)
    except RuntimeError as exc:
        assert "outside the approved provider-bound range" in str(exc)
    else:
        raise AssertionError("wrong range must be rejected")
