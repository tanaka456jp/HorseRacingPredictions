"""Offline, synthetic-tested RA/SE multi-shard pre2025 *research* staging.

Never invoked by PC2 Actions. No licence inference, JRA-VAN calls, betting,
note publication or final 2025-26 holdout use. Every input is FULLY audited
before ANY staged output is created. SQLite is local-only and bounded output
CSV partitions remain unapproved research candidates (NOT ready to train).
"""
from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Sequence

from .jravan_parser import (
    CENTRAL_RACECOURSES, DATA_PRIORITY, parse_ra, parse_se,
)
from .pre2025_jsonl_chronology_audit import audit_pre2025_ra_se_jsonl
from .pre2025_training_csv_audit import (
    MAX_BYTES as MAX_CSV_BYTES, UnsafeTrainingSource,
    audit_pre2025_training_csv,
)

_MAX_SHARDS = 12
_MAX_TOTAL_SOURCE_BYTES = 12_000_000_000
_MAX_OUTPUT_ROWS = 3_000_000
_FIELDNAMES = (
    "race_id", "race_date", "horse_name", "finish_position",
    "racecourse", "surface", "distance_m", "weather", "track_condition",
    "post_position", "sex", "age", "carried_weight", "jockey",
    "trainer", "horse_weight", "horse_weight_delta", "last_3f",
    "corner_1", "corner_2", "corner_3", "corner_4",
    "race_class", "graded_race",
)


@dataclass(frozen=True)
class Pre2025AssemblyResult:
    status: str
    source_shards: int
    source_ra_records: int
    source_se_records: int
    saved_races: int
    saved_runners: int
    excluded_incomplete_races: int
    output_years: tuple[int, ...]
    model_training_started: bool = False
    operator_rights_attested: bool = False
    independently_verified_licence: bool = False
    source_right_to_redistribute: bool = False
    protected_2025_2026_holdout_used: bool = False
    publication_authorized: bool = False


def _candidate_source(path: Path) -> None:
    if not path.is_absolute() or path.suffix.lower() != ".jsonl":
        raise UnsafeTrainingSource("ABSOLUTE_HISTORICAL_JSONL_REQUIRED")
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise UnsafeTrainingSource("UNTRUSTED_SOURCE_SHARD")
    if any(part.lower() in {
        "jravan-private-quarantine", "holdout", "final-evaluation",
        "2025-2026-holdout", "protected-holdout",
    } for part in path.parts):
        raise UnsafeTrainingSource("PROTECTED_SOURCE_FOLDER_FORBIDDEN")


def _priority(division: str) -> int:
    return DATA_PRIORITY.get(division, -1)


def _upsert(conn: sqlite3.Connection, table: str, race_id: str,
            horse_key: str | None, payload: dict, division: str) -> None:
    key = horse_key or ""
    # Cannot model source ordering from a fabricated race identity. Each
    # race/horse key is stable through sequential data-division updates.
    stored = conn.execute(
        "SELECT priority FROM " + table + " WHERE race_id=? AND horse_key=?",
        (race_id, key),
    ).fetchone()
    rank = _priority(division)
    if stored is not None and rank < stored[0]:
        return
    conn.execute(
        "INSERT OR REPLACE INTO " + table
        + " (race_id, horse_key, priority, body) VALUES (?,?,?,?)",
        (race_id, key, rank, json.dumps(payload, ensure_ascii=False)),
    )


def _make_row(race: dict, horse: dict) -> dict:
    result = {
        "race_id": race["race_id"],
        "race_date": race["race_date"],
        "horse_name": horse["horse_name"],
        "finish_position": horse["finish_position"],
    }
    for name in _FIELDNAMES:
        if name not in result:
            result[name] = horse.get(name) if name in {
                "post_position", "sex", "age", "carried_weight",
                "jockey", "trainer", "horse_weight", "horse_weight_delta",
                "last_3f", "corner_1", "corner_2", "corner_3", "corner_4",
            } else race.get(name)
    return result


def stage_pre2025_ra_se_shards(
    sources: Sequence[Path], *, destination: Path,
) -> Pre2025AssemblyResult:
    """Make a *new* private research staging dir, never an approved dataset.

    Local operator must separately verify legitimate source rights and then
    perform independent chronological research gate checks. Merely creating
    these files authorizes neither modeling nor publishing.
    """
    if (not isinstance(sources, (list, tuple))
            or not 1 <= len(sources) <= _MAX_SHARDS
            or any(not isinstance(p, Path) for p in sources)):
        raise UnsafeTrainingSource("EXPLICIT_SHARD_PATH_LIST_REQUIRED")
    if len(set(sources)) != len(sources):
        raise UnsafeTrainingSource("DUPLICATE_SOURCE_SHARD")
    if (not isinstance(destination, Path)
            or not destination.is_absolute()
            or destination.exists() or destination.is_symlink()
            or not destination.parent.is_dir()
            or destination.parent.is_symlink()
            or any(part.lower() in {
                "jravan-private-quarantine", "holdout", "final-evaluation",
            } for part in destination.parts)):
        raise UnsafeTrainingSource("NEW_PRIVATE_OUTPUT_DIRECTORY_REQUIRED")

    # Pass one: audit ALL sources, including rows far beyond 256KiB, before
    # creating any output. Source rights are NOT established by a successful
    # chronology check.
    audits = []
    total_bytes = 0
    for path in sources:
        _candidate_source(path)
        total_bytes += path.stat().st_size
        if total_bytes > _MAX_TOTAL_SOURCE_BYTES:
            raise UnsafeTrainingSource("HISTORICAL_ARCHIVE_SIZE_LIMIT")
        audits.append(audit_pre2025_ra_se_jsonl(path))
    if not any(a.ra_records for a in audits) or not any(
        a.se_records for a in audits
    ):
        raise UnsafeTrainingSource("NO_MATCHABLE_RA_AND_SE")
    destination.mkdir()
    (destination / "INCOMPLETE_DO_NOT_USE").write_text(
        "Local research candidate only; no licence, modeling or note rights.",
        encoding="utf-8",
    )
    conn = sqlite3.connect(str(destination / "private_staging.sqlite"))
    try:
        conn.execute(
            "CREATE TABLE races (race_id TEXT NOT NULL,"
            "horse_key TEXT NOT NULL, priority INTEGER NOT NULL,"
            "body TEXT NOT NULL, PRIMARY KEY(race_id, horse_key))"
        )
        conn.execute(
            "CREATE TABLE horses (race_id TEXT NOT NULL,"
            "horse_key TEXT NOT NULL, priority INTEGER NOT NULL,"
            "body TEXT NOT NULL, PRIMARY KEY(race_id, horse_key))"
        )
        for path in sources:
            with path.open("r", encoding="utf-8-sig") as stream:
                for line in stream:
                    # Inputs were previously exhaustively verified.
                    item = json.loads(line)
                    kind = item.get("record_type")
                    if kind not in ("RA", "SE"):
                        continue
                    if kind == "RA":
                        race = parse_ra(item["text"])
                        if race.racecourse_code in CENTRAL_RACECOURSES:
                            _upsert(conn, "races", race.race_id, "",
                                    asdict(race), race.data_division)
                    else:
                        horse = parse_se(item["text"])
                        if not horse.horse_name.strip():
                            raise UnsafeTrainingSource("HORSE_IDENTITY_MISSING")
                        _upsert(conn, "horses", horse.race_id,
                                horse.horse_name.strip(),
                                asdict(horse), horse.data_division)
            conn.commit()
        # Staged research export is year-partitioned for the existing
        # <=400MB strict trainer; no market/popularity fields are exported.
        cursor = conn.execute(
            "SELECT r.body, h.body FROM races r JOIN horses h"
            " ON r.race_id=h.race_id"
            " ORDER BY r.race_id, h.horse_key"
        )
        current_race = None
        group: list[tuple[dict, dict]] = []
        saved_races = 0
        saved_rows = 0
        excluded = 0
        year_files: dict[int, tuple[Path, object, csv.DictWriter, int]] = {}

        def commit_race() -> None:
            nonlocal saved_races, saved_rows, excluded
            if not group:
                return
            race = group[0][0]
            year = int(race["race_date"][:4])
            finishes = [h["finish_position"] for _, h in group]
            names = [h["horse_name"].strip() for _, h in group]
            if (not 4 <= len(group) <= 18
                    or any(type(p) is not int or p < 1 or p > len(group)
                           for p in finishes)
                    or finishes.count(1) != 1
                    or len(set(names)) != len(names)
                    or year > 2024):
                excluded += 1
                return
            if year not in year_files:
                path = destination / f"research_{year}.csv"
                handle = path.open("x", encoding="utf-8", newline="")
                writer = csv.DictWriter(
                    handle, fieldnames=_FIELDNAMES, extrasaction="raise",
                )
                writer.writeheader()
                year_files[year] = (path, handle, writer, 0)
            path, handle, writer, n = year_files[year]
            if n + len(group) > _MAX_OUTPUT_ROWS:
                raise UnsafeTrainingSource("YEARLY_RESEARCH_ROW_CAP")
            for r, h in group:
                writer.writerow(_make_row(r, h))
            n += len(group)
            saved_races += 1
            saved_rows += len(group)
            year_files[year] = (path, handle, writer, n)
            if handle.tell() > 380_000_000:
                raise UnsafeTrainingSource("YEARLY_CSV_SAFETY_MARGIN_EXCEEDED")

        try:
            for raw_race, raw_horse in cursor:
                race = json.loads(raw_race)
                horse = json.loads(raw_horse)
                if current_race is not None and race["race_id"] != current_race:
                    commit_race()
                    group.clear()
                current_race = race["race_id"]
                group.append((race, horse))
            commit_race()
        finally:
            for path, handle, writer, n in year_files.values():
                handle.close()
        if not saved_races:
            raise UnsafeTrainingSource("NO_COMPLETE_TRAINING_RACES")
        files = []
        for year, (path, handle, _, _) in sorted(year_files.items()):
            audit = audit_pre2025_training_csv(path)
            files.append({
                "year": year, "rows": audit.checked_rows,
                "sha256": audit.sha256,
                "bytes": path.stat().st_size,
            })
        receipt = {
            "schemaVersion": 1,
            "status": "PRIVATE_RESEARCH_STAGING_SOURCE_RIGHTS_PENDING",
            "sourceSha256": [a.sha256 for a in audits],
            "candidateYearlyCsv": files,
            "sourceRaCount": sum(a.ra_records for a in audits),
            "sourceSeCount": sum(a.se_records for a in audits),
            "savedRaces": saved_races,
            "savedRunners": saved_rows,
            "excludedIncompleteRaces": excluded,
            "trainWithoutSeparateSourceApproval": False,
            "sourceRightsIndependentlyVerified": False,
            "protectedHoldoutTrainingAllowed": False,
            "publicationAuthorized": False,
            "notePostAttempted": False,
        }
        (destination / "private_research_manifest.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (destination / "INCOMPLETE_DO_NOT_USE").rename(
            destination / "REVIEW_ONLY_NOT_APPROVED_FOR_TRAINING"
        )
        return Pre2025AssemblyResult(
            status="PRIVATE_RESEARCH_STAGING_SOURCE_RIGHTS_PENDING",
            source_shards=len(sources),
            source_ra_records=sum(a.ra_records for a in audits),
            source_se_records=sum(a.se_records for a in audits),
            saved_races=saved_races, saved_runners=saved_rows,
            excluded_incomplete_races=excluded,
            output_years=tuple(sorted(year_files)),
        )
    finally:
        conn.close()
