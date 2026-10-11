import hashlib
import json
from pathlib import Path

from horse_racing_predictions.jravan_archive_migration import (
    migrate_archive_to_preferred_storage,
)
from horse_racing_predictions.jravan_archive_paths import (
    ARCHIVE_ROOT_ENV,
    default_archive_root,
    legacy_localappdata_archive_root,
)
from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)
from horse_racing_predictions.jravan_free_trial_archive import (
    DEFAULT_ARCHIVE_RANGE,
)


def _make_source(root: Path) -> tuple[Path, str]:
    root.mkdir(parents=True)
    raw = root / "bldn_raw.jsonl"
    raw.write_bytes(b'{"record_type":"SK","text":"synthetic"}\n')
    digest = hashlib.sha256(raw.read_bytes()).hexdigest()

    legacy = {
        "status": "partial",
        "jvopen_range": DEFAULT_ARCHIVE_RANGE,
        "raw_redistribution_allowed": False,
        "protected_holdout": "2025-2026 untouched",
        "parts": [{
            "dataspec": "BLDN",
            "status": "success",
            "records_written": 1,
            "output_sha256": digest,
            "output_path": str(raw),
            "last_file_timestamp": "20241229143624",
            "research_use_allowed": True,
        }],
    }
    (root / "latest_manifest.json").write_text(
        json.dumps(legacy),
        encoding="utf-8",
    )
    v2 = dict(legacy)
    v2["manifest_version"] = 2
    (root / "latest_manifest_v2.json").write_text(
        json.dumps(v2),
        encoding="utf-8",
    )
    return raw, digest


def test_archive_root_environment_override_wins(tmp_path):
    env = {
        "LOCALAPPDATA": str(tmp_path / "local"),
        ARCHIVE_ROOT_ENV: str(tmp_path / "custom"),
    }
    assert default_archive_root(env) == tmp_path / "custom"


def test_legacy_archive_root_remains_localappdata_based(tmp_path):
    env = {"LOCALAPPDATA": str(tmp_path / "local")}
    assert legacy_localappdata_archive_root(env) == (
        tmp_path
        / "local"
        / "HorseRacingPredictions"
        / "JraVanFreeTrialArchive"
        / "pre2025"
    )


def test_verified_migration_rewrites_manifest_to_destination_and_keeps_source_by_default(
    tmp_path,
):
    source = tmp_path / "c-archive"
    destination = tmp_path / "d-archive"
    _, digest = _make_source(source)

    report = migrate_archive_to_preferred_storage(
        source_root=source,
        destination_root=destination,
        delete_source_after_verify=False,
        min_free_margin_bytes=0,
    )

    assert report.status == "verified"
    assert report.source_deleted_after_verify is False
    assert source.is_dir()
    assert destination.is_dir()

    provenance = validate_local_pre2025_archive(
        destination,
        required_dataspecs=("BLDN",),
    )
    assert provenance.parts[0].sha256 == digest
    assert provenance.parts[0].path == (
        destination / "bldn_raw.jsonl"
    ).resolve()

    migrated_v2 = json.loads(
        (destination / "latest_manifest_v2.json").read_text(
            encoding="utf-8"
        )
    )
    assert migrated_v2["parts"][0]["output_path"] == str(
        destination / "bldn_raw.jsonl"
    )
    assert (
        migrated_v2["migration"]["migrated_from_legacy_localappdata"]
        is True
    )


def test_delete_source_occurs_only_after_verified_destination(tmp_path):
    source = tmp_path / "c-archive"
    destination = tmp_path / "d-archive"
    _, digest = _make_source(source)

    report = migrate_archive_to_preferred_storage(
        source_root=source,
        destination_root=destination,
        delete_source_after_verify=True,
        min_free_margin_bytes=0,
    )

    assert report.source_deleted_after_verify is True
    assert report.source_tombstone_written is True
    assert not (source / "bldn_raw.jsonl").exists()
    assert (source / "MOVED_TO_D.json").is_file()
    assert (destination / "bldn_raw.jsonl").is_file()
    assert hashlib.sha256(
        (destination / "bldn_raw.jsonl").read_bytes()
    ).hexdigest() == digest

    receipt = json.loads(
        (destination / "migration_receipt.json").read_text(
            encoding="utf-8"
        )
    )
    assert receipt["source_deleted_after_verify"] is True
    assert receipt["protected_holdout"] == "2025-2026 untouched"
