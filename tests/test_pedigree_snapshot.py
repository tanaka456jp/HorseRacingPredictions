import json

import pytest

from horse_racing_predictions.pedigree_snapshot import (
    build_pedigree_snapshot,
)


def _put(raw: bytearray, position: int, length: int, value: str) -> None:
    encoded = value.encode("ascii")
    start = position - 1
    raw[start:start + length] = encoded.ljust(length, b" ")


def _sk(
    *,
    division="1",
    created="20240101",
    blood="2020A00001",
    sire="SIRE000001",
    dam="DAM0000001",
    damsire="DMSIRE0001",
):
    raw = bytearray(b" " * 206)
    _put(raw, 1, 2, "SK")
    _put(raw, 3, 1, division)
    _put(raw, 4, 8, created)
    _put(raw, 12, 10, blood)
    _put(raw, 22, 8, "20200315")
    _put(raw, 30, 1, "1")
    _put(raw, 31, 1, "1")
    _put(raw, 32, 2, "01")
    _put(raw, 34, 1, "0")
    _put(raw, 35, 4, "0000")
    _put(raw, 39, 8, "00000001")
    pedigree = [
        sire,
        dam,
        "SSIRE00001",
        "SDAM000001",
        damsire,
        "DMDAM00001",
        "SSSIRE0001",
        "SSDAM00001",
        "SDSIRE0001",
        "SDDAM00001",
        "DSSIRE0001",
        "DSDAM00001",
        "DDSIRE0001",
        "DDDAM00001",
    ]
    for index, value in enumerate(pedigree):
        _put(raw, 67 + index * 10, 10, value)
    return raw.decode("ascii")


def _write(path, records):
    path.write_text(
        "\n".join(
            json.dumps({"record_type": "SK", "text": text})
            for text in records
        )
        + "\n",
        encoding="utf-8",
    )


def test_snapshot_replays_old_and_new_archives_and_reports_only_aggregates(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    _write(
        root / "blod_raw.jsonl",
        [
            _sk(
                created="20200101",
                blood="2020A00001",
                sire="SIRE000001",
            ),
            _sk(
                created="20200101",
                blood="2020A00002",
                sire="SIRE000002",
            ),
        ],
    )
    _write(
        root / "bldn_raw.jsonl",
        [
            _sk(
                division="2",
                created="20240101",
                blood="2020A00001",
                sire="SIRE000003",
            ),
            _sk(
                division="0",
                created="20240201",
                blood="2020A00002",
                sire="SIRE000002",
            ),
        ],
    )

    snapshot = root / "pedigree_snapshot.csv"
    report_path = tmp_path / "report.json"
    report = build_pedigree_snapshot(
        archive_root=root,
        snapshot_path=snapshot,
        report_path=report_path,
    )

    assert report.status == "ready"
    assert report.rows == 1
    assert report.sire_rows == 1
    assert report.damsire_rows == 1
    assert report.input_files == (
        "blod_raw.jsonl",
        "bldn_raw.jsonl",
    )
    assert len(report.snapshot_sha256) == 64
    assert report.raw_identifiers_uploaded is False
    assert report.protected_holdout == "2025-2026 untouched"

    saved_report = report_path.read_text(encoding="utf-8")
    assert "SIRE000003" not in saved_report
    assert "2020A00001" not in saved_report

    local_snapshot = snapshot.read_text(encoding="utf-8-sig")
    assert "SIRE000003" in local_snapshot
    assert "2020A00002" not in local_snapshot


def test_snapshot_rejects_any_post2024_sk_record(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    _write(
        root / "bldn_raw.jsonl",
        [
            _sk(
                created="20250101",
                blood="2020A00001",
            )
        ],
    )

    with pytest.raises(RuntimeError, match="post-2024"):
        build_pedigree_snapshot(
            archive_root=root,
            snapshot_path=root / "pedigree_snapshot.csv",
            report_path=tmp_path / "report.json",
        )


def test_snapshot_requires_local_blood_archive(tmp_path):
    with pytest.raises(FileNotFoundError, match="BLOD/BLDN"):
        build_pedigree_snapshot(
            archive_root=tmp_path / "empty",
            snapshot_path=tmp_path / "snapshot.csv",
            report_path=tmp_path / "report.json",
        )
