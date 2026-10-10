"""Build a local pedigree snapshot from archived BLOD/BLDN JV-Data.

The snapshot stays on the Windows runner. The sanitized report contains only
aggregate coverage and hashes, never blood/breeding registration identifiers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

import pandas as pd

from .jravan_pedigree import load_sk_pedigree_jsonl_many


MAX_PEDIGREE_CREATED_DATE = "20241231"


@dataclass(frozen=True)
class PedigreeSnapshotReport:
    status: str
    rows: int
    sire_rows: int
    damsire_rows: int
    sire_coverage: float
    damsire_coverage: float
    unique_sires: int
    unique_damsires: int
    created_date_min: str | None
    created_date_max: str | None
    snapshot_sha256: str
    input_files: tuple[str, ...]
    protected_holdout: str
    raw_identifiers_uploaded: bool


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_pedigree_archives(
    archive_root: str | Path,
) -> tuple[Path, ...]:
    root = Path(archive_root)
    ordered = (
        root / "blod_raw.jsonl",
        root / "bldn_raw.jsonl",
    )
    return tuple(path for path in ordered if path.is_file())


def build_pedigree_snapshot(
    *,
    archive_root: str | Path,
    snapshot_path: str | Path,
    report_path: str | Path,
) -> PedigreeSnapshotReport:
    inputs = discover_pedigree_archives(archive_root)
    if not inputs:
        raise FileNotFoundError(
            "No local BLOD/BLDN archive exists; raw provider data must be "
            "captured locally before building a pedigree snapshot."
        )

    frame = load_sk_pedigree_jsonl_many(inputs)
    if frame.empty:
        raise RuntimeError(
            "BLOD/BLDN archives contained no active SK pedigree records."
        )

    created = frame["pedigree_created_date"].astype("string").fillna("")
    bad_format = ~created.str.fullmatch(r"\d{8}")
    if bad_format.any():
        raise ValueError(
            "Pedigree snapshot contains malformed SK created dates."
        )
    if (created > MAX_PEDIGREE_CREATED_DATE).any():
        raise RuntimeError(
            "Pedigree snapshot contains post-2024 SK records; protected "
            "2025-2026 holdout boundary would be violated."
        )

    snapshot_path = Path(snapshot_path)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    staging = snapshot_path.with_suffix(snapshot_path.suffix + ".partial")
    frame.to_csv(
        staging,
        index=False,
        encoding="utf-8-sig",
    )
    digest = _sha256(staging)
    staging.replace(snapshot_path)

    sire = (
        frame["sire_breeding_registration_number"]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    damsire = (
        frame["damsire_breeding_registration_number"]
        .astype("string")
        .fillna("")
        .str.strip()
    )
    sire_rows = int(sire.ne("").sum())
    damsire_rows = int(damsire.ne("").sum())
    rows = int(len(frame))

    report = PedigreeSnapshotReport(
        status="ready",
        rows=rows,
        sire_rows=sire_rows,
        damsire_rows=damsire_rows,
        sire_coverage=sire_rows / rows,
        damsire_coverage=damsire_rows / rows,
        unique_sires=int(sire[sire.ne("")].nunique()),
        unique_damsires=int(damsire[damsire.ne("")].nunique()),
        created_date_min=str(created.min()),
        created_date_max=str(created.max()),
        snapshot_sha256=digest,
        input_files=tuple(path.name for path in inputs),
        protected_holdout="2025-2026 untouched",
        raw_identifiers_uploaded=False,
    )

    report_path = Path(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
