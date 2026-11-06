"""NAR official monthly ZIP: local-only aggregate CSV header-shape probe.

Never emit any CSV header text, horse/race identity, ZIP path, exception or
raw bytes. Only 3 fixed member kinds, aggregate widths and boolean flags.
Requires operator confirmation of lawful personal use. No download, upload,
archive extraction, filesystem changes, training or payout ROI evaluation.
"""
from __future__ import annotations

import argparse
import csv
from io import StringIO
import json
from pathlib import Path
import re
from zipfile import ZipFile

from horse_racing_predictions.nar_official_zip_probe import (
    _ZIP_RE, _CSV_RE, UnsafeNarSource, inspect_nar_monthly_zip_structure,
)
from horse_racing_predictions.nar_local_monthly_intake import _decoded_csv
from horse_racing_predictions.nar_published_result_normalizer import (
    _EXPECTED_WIDTH, _HEADER_PREFIX,
)

_MONTHS = frozenset(f"{year}{month:02d}" for year in range(2017, 2023)
                    for month in range(1, 13))
_CSV_LIMIT = 16_000_000
_STATIC = re.compile(r"NAR_[A-Z0-9_]{1,90}\Z")


def inspect_header_shape(path: Path, *, month: str, permission_confirmed: bool) -> dict:
    if permission_confirmed is not True:
        raise UnsafeNarSource("NAR_PERSONAL_RESEARCH_PERMISSION_REQUIRED")
    if month not in _MONTHS:
        raise UnsafeNarSource("NAR_PROTECTED_OR_UNEXPECTED_TRAINING_MONTH")
    if not isinstance(path, Path) or not path.is_absolute():
        raise UnsafeNarSource("NAR_ABSOLUTE_LOCAL_ZIP_REQUIRED")
    name_match = _ZIP_RE.fullmatch(path.name)
    if name_match is None or name_match.group(1) != month:
        raise UnsafeNarSource("NAR_WRONG_MONTHLY_ARCHIVE_NAME")
    inspect_nar_monthly_zip_structure(path)
    aggregate = []
    with ZipFile(path) as zf:
        for kind in sorted(_EXPECTED_WIDTH):
            exact_name = f"{month}_{kind}.csv"
            info = zf.getinfo(exact_name)
            if info.file_size > _CSV_LIMIT or info.file_size < 1:
                raise UnsafeNarSource("NAR_PROBE_CSV_SIZE_BOUNDS")
            with zf.open(info) as stream:
                raw = stream.read(_CSV_LIMIT + 1)
            if len(raw) != info.file_size:
                raise UnsafeNarSource("NAR_PROBE_CSV_SIZE_BOUNDS")
            text = _decoded_csv(raw)
            reader = csv.reader(StringIO(text.lstrip("\ufeff"), newline=""), strict=True)
            first = next(reader, [])
            second = next(reader, [])
            headers = [cell.strip().lstrip("\ufeff") for cell in first]
            prefix = tuple(headers[:3]) == _HEADER_PREFIX
            aggregate.append({
                "kind": kind,
                "expectedWidth": _EXPECTED_WIDTH[kind],
                "firstRecordWidth": len(first),
                "secondRecordWidth": len(second),
                "hasOfficialHeaderPrefix": prefix,
                "duplicateHeaderCells": (
                    len(headers) - len(set(headers)) if prefix else None
                ),
                "emptyHeaderCells": (
                    sum(not cell for cell in headers) if prefix else None
                ),
                "prefixAndWidthMatch": prefix and len(first) == _EXPECTED_WIDTH[kind],
            })
    return {
        "status": "NAR_LOCAL_HEADER_SHAPE_ONLY",
        "month": month,
        "members": aggregate,
        "sourceTextExported": False,
        "preEventSnapshotProven": False,
        "trainingExecuted": False,
        "positiveEvDemonstrated": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-monthly-race-zip", type=Path, required=True)
    parser.add_argument("--expected-month", required=True)
    parser.add_argument("--confirm-personal-private-nar-permission",
                        action="store_true")
    args = parser.parse_args()
    try:
        doc = inspect_header_shape(
            args.local_monthly_race_zip, month=args.expected_month,
            permission_confirmed=args.confirm_personal_private_nar_permission,
        )
    except Exception as exc:
        code = str(exc) if isinstance(exc, UnsafeNarSource) else ""
        if not _STATIC.fullmatch(code):
            code = "NAR_LOCAL_HEADER_PROBE_BLOCKED"
        doc = {
            "status": "NAR_LOCAL_HEADER_PROBE_BLOCKED",
            "reasonCode": code,
            "sourceTextExported": False,
            "trainingExecuted": False,
            "positiveEvDemonstrated": False,
        }
    print(json.dumps(doc, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if doc["status"] == "NAR_LOCAL_HEADER_SHAPE_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
