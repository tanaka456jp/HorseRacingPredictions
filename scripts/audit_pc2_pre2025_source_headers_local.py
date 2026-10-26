"""PC2 approved pre2025 archive header and bounded date sample audit.

Samples at most 256 KiB per candidate source without modifying files. Never
uploads source bytes, filenames, horse identities, odds, keys or raw records.
A sampled header/date audit is NOT a full chronology or licence approval.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import io
import json
import os
from pathlib import Path
import platform
import struct

ROOT = Path("D:/JRA-VAN/Data Lab/archive/pre2025")
MAX_FILES = 100
MAX_SAMPLE_BYTES = 262_144
YEAR_CUTOFF = 2024
EXTENSIONS = frozenset({".csv", ".jsonl"})


@dataclass
class SampleSummary:
    schemaVersion: int = 1
    status: str = "BLOCKED"
    stage: str = "NOT_STARTED"
    verifiedPhysicalPC2: bool = False
    selectedPythonBits: int = 0
    scannedFiles: int = 0
    csvFiles: int = 0
    jsonlFiles: int = 0
    csvHeaderPotentiallyUsable: int = 0
    sampledRecordRows: int = 0
    sampledPre2025DateRows: int = 0
    sampled2025OrLaterDateRows: int = 0
    sampledInvalidOrUnknownDates: int = 0
    sampledRaRecordTypes: int = 0
    sampledSeRecordTypes: int = 0
    allRowsChronologicallyVerified: bool = False
    licensedPrivateResearchUseIndependentlyVerified: bool = False
    sourceRightToRedistributeVerified: bool = False
    readyForTraining: bool = False
    protectedHoldoutTrainingAllowed: bool = False
    publicationAuthorized: bool = False
    dataMovedOrChanged: bool = False
    rawDataUploaded: bool = False
    horseIdentityOrFilenameUploaded: bool = False
    usageKeyRead: bool = False


def _year(text: str) -> int | None:
    try:
        s = text.strip().replace("/", "-")
        if len(s) >= 4 and s[0:4].isdigit():
            year = int(s[:4])
            if 1980 <= year <= 2100:
                return year
    except (ValueError, AttributeError):
        pass
    return None


def _record_year(payload: dict) -> int | None:
    d = payload.get("race_date")
    if isinstance(d, str):
        return _year(d)
    data = payload.get("text")
    if not isinstance(data, str):
        return None
    try:
        raw = data.encode("cp932", errors="strict")
        if len(raw) >= 15 and raw[11:15].isdigit():
            return _year(raw[11:15].decode("ascii"))
    except (UnicodeError, ValueError):
        pass
    return None


def _consume_year(report: SampleSummary, year: int | None) -> None:
    report.sampledRecordRows += 1
    if year is None:
        report.sampledInvalidOrUnknownDates += 1
    elif year > YEAR_CUTOFF:
        report.sampled2025OrLaterDateRows += 1
    else:
        report.sampledPre2025DateRows += 1


def _inspect_csv(data: bytes, report: SampleSummary) -> None:
    # Partial sample, UTF8/CP932 best effort. Never emit decoded field values.
    decoded = None
    for encoding in ("utf-8-sig", "cp932"):
        try:
            decoded = data.decode(encoding, errors="strict")
            break
        except UnicodeDecodeError:
            pass
    if decoded is None:
        report.sampledInvalidOrUnknownDates += 1
        return
    try:
        rows = iter(csv.reader(io.StringIO(decoded)))
        header = next(rows)
    except (csv.Error, StopIteration):
        report.sampledInvalidOrUnknownDates += 1
        return
    cols = [h.strip() for h in header]
    if len(cols) != len(set(cols)):
        return
    col_aliases = {
        "race_id": {"race_id", "レースID", "Race ID"},
        "race_date": {"race_date", "レース日付", "Race Day"},
        "horse_name": {"horse_name", "馬名", "Horse Name"},
        "finish_position": {"finish_position", "着順", "FP"},
    }
    if all(any(name in allowed for name in cols)
           for allowed in col_aliases.values()):
        report.csvHeaderPotentiallyUsable += 1
    date_index = next(
        (i for i, h in enumerate(cols)
         if h in col_aliases["race_date"]), None
    )
    for row in rows:
        if report.sampledRecordRows >= 1000:
            break
        if date_index is None or len(row) != len(cols):
            _consume_year(report, None)
        else:
            _consume_year(report, _year(row[date_index]))


def _inspect_jsonl(data: bytes, report: SampleSummary) -> None:
    lines = data.splitlines()
    # Discard last line: it might end mid-object due to read bound.
    for line in lines[:-1][:64]:
        if report.sampledRecordRows >= 1000:
            break
        try:
            obj = json.loads(line.decode("utf-8-sig"))
            if not isinstance(obj, dict):
                _consume_year(report, None)
                continue
            t = obj.get("record_type")
            if t == "RA":
                report.sampledRaRecordTypes += 1
            elif t == "SE":
                report.sampledSeRecordTypes += 1
            _consume_year(report, _record_year(obj))
        except (UnicodeError, ValueError, TypeError, json.JSONDecodeError):
            _consume_year(report, None)


def inspect_archive_sample(
    *, output: Path, root: Path = ROOT,
    computer: str | None = None,
    bits: int | None = None,
    windows: bool | None = None,
) -> dict:
    if computer is None:
        computer = os.getenv("COMPUTERNAME", "")
    if bits is None:
        bits = struct.calcsize("P") * 8
    if windows is None:
        windows = platform.system() == "Windows"
    report = SampleSummary(
        verifiedPhysicalPC2=computer == "DESKTOP-MVV1FD4",
        selectedPythonBits=bits,
    )
    try:
        if not (windows and bits == 64 and computer == "DESKTOP-MVV1FD4"):
            report.stage = "PC2_PYTHON64_REQUIRED"
            return asdict(report)
        if root.is_symlink() or not root.is_dir():
            report.stage = "PRE2025_ARCHIVE_MISSING_OR_LINKED"
            return asdict(report)
        candidates = []
        folders = [root]
        for dir_ in root.iterdir():
            if dir_.is_dir() and not dir_.is_symlink():
                folders.append(dir_)
        for folder in folders:
            for f in folder.iterdir():
                if f.is_file() and not f.is_symlink() and f.suffix.lower() in EXTENSIONS:
                    candidates.append(f)
                    if len(candidates) > MAX_FILES:
                        raise ValueError("TOO_MANY_ARCHIVE_FILES")
        report.scannedFiles = len(candidates)
        for f in candidates:
            if f.suffix.lower() == ".csv":
                report.csvFiles += 1
            else:
                report.jsonlFiles += 1
            with f.open("rb") as h:
                head = h.read(MAX_SAMPLE_BYTES)
            if f.suffix.lower() == ".csv":
                _inspect_csv(head, report)
            else:
                _inspect_jsonl(head, report)
        report.stage = "BOUNDED_HEADER_AND_DATE_SAMPLE_FINISHED"
        report.status = "METADATA_SAMPLED_NOT_APPROVED_FOR_TRAINING"
    except (OSError, ValueError, TypeError):
        report.status = "BLOCKED"
        report.stage = "METADATA_SAMPLING_INCOMPLETE"
    finally:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(asdict(report), sort_keys=True), encoding="utf-8"
        )
    return asdict(report)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sanitized-output", required=True, type=Path)
    args = p.parse_args()
    inspect_archive_sample(output=args.sanitized_output)


if __name__ == "__main__":
    main()
