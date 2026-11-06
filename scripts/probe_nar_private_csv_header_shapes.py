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
from itertools import chain
import json
from pathlib import Path
import re
import unicodedata
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



# All categories are hardcoded; never print a private cell or race identity.
_FINISH_MARKERS = {
    "取消": "SCRATCH", "出走取消": "SCRATCH",
    "除外": "EXCLUDED", "競走除外": "EXCLUDED",
    "中止": "DID_NOT_FINISH", "競走中止": "DID_NOT_FINISH",
    "失格": "DISQUALIFIED",
    "取止": "RACE_CANCELLED", "競走取止": "RACE_CANCELLED",
    "競走取り止め": "RACE_CANCELLED",
    "不成": "NO_CONTEST", "競走不成立": "NO_CONTEST",
}


def _safe_finish_bucket(value: str) -> str:
    """Return only a bounded, predefined *category*, never a source value."""
    normalized = "".join(
        c for c in unicodedata.normalize("NFKC", value) if not c.isspace()
    )
    if normalized.isascii() and normalized.isdecimal():
        return ("NUMERIC_RANK" if len(normalized) <= 2
                and 1 <= int(normalized) <= 18 else "OTHER_NUMBER")
    if not normalized:
        return "BLANK"
    if normalized in _FINISH_MARKERS:
        return _FINISH_MARKERS[normalized]
    if normalized.endswith(("降", "降着")):
        digits = normalized[:-1] if normalized.endswith("降") else normalized[:-2]
        if digits.isascii() and digits.isdecimal() and 1 <= int(digits) <= 18:
            return "DEMOTED"
    return "OTHER_TEXT"

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
    flat_finish_counts = {}
    flat_finish_races = {}
    flat_horse_rows = 0
    flat_rank_profiles = {}  # race-keyed only in ephemeral memory
    flat_declared_counts = {}
    flat_payback_rows = {}
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
            position_counts = None
            if kind == "payback":
                for row in chain([second], reader):
                    if len(row) == _EXPECTED_WIDTH[kind] and "帯広" not in row[0]:
                        flat_payback_rows.setdefault(tuple(row[:3]), []).append(tuple(row))
            if kind == "horselist":
                for row in chain([second], reader):
                    if not row or len(row) != _EXPECTED_WIDTH[kind]:
                        continue  # width is separately disclosed, never guessed
                    if "帯広" in row[0]:
                        continue  # predeclared venue-level banei exclusion
                    flat_horse_rows += 1
                    category = _safe_finish_bucket(row[31])
                    profile = flat_rank_profiles.setdefault(tuple(row[:3]), {
                        "ranked": [], "blank": 0, "all": 0,
                        "blankTime": 0, "blankPopularity": 0,
                    })
                    profile["all"] += 1
                    if category == "NUMERIC_RANK":
                        profile["ranked"].append(int(unicodedata.normalize("NFKC", row[31])))
                    elif category == "BLANK":
                        profile["blank"] += 1
                        profile["blankTime"] += bool(row[32].strip())
                        profile["blankPopularity"] += bool(row[35].strip())
                    flat_finish_counts[category] = flat_finish_counts.get(category, 0) + 1
                    if category != "NUMERIC_RANK":
                        # Keys exist *only* in process memory. Never serialize.
                        key = tuple(row[:3])
                        flat_finish_races.setdefault(category, set()).add(key)
            if kind == "racelist":
                # Inspect only schema/semantic counts, never text values.
                position_counts = {
                    "records": 0,
                    "rowWidthCounts": {},
                    "flatVenueRecords": 0,
                    "flatVenueSurfaceAt21": 0,
                    "flatVenueDistanceAt23": 0,
                    "flatVenueStartersAt26": 0,
                    "baneiVenueRecords": 0,
                    "venueContainsBaneiNameRecords": 0,
                    "nonstandardSurfaceRecords": 0,
                    "nonstandardSurfaceAtBaneiNamedVenue": 0,
                }
                for row in chain([second], reader):
                    if not row:
                        continue
                    position_counts["records"] += 1
                    if position_counts["records"] > 250000:
                        raise UnsafeNarSource("NAR_PROBE_TOO_MANY_RACES")
                    width = str(len(row))
                    widths = position_counts["rowWidthCounts"]
                    widths[width] = widths.get(width, 0) + 1
                    has_banei_name = "帯広" in row[0]
                    if has_banei_name:
                        position_counts["venueContainsBaneiNameRecords"] += 1
                    if row[0].strip() == "帯広":
                        position_counts["baneiVenueRecords"] += 1
                    if len(row) > 26 and row[21].strip() not in {"芝", "ダート"}:
                        position_counts["nonstandardSurfaceRecords"] += 1
                        if has_banei_name:
                            position_counts["nonstandardSurfaceAtBaneiNamedVenue"] += 1
                    if has_banei_name:
                        continue
                    if len(row) > 26 and row[26].strip().isascii() and row[26].strip().isdecimal():
                        flat_declared_counts[tuple(row[:3])] = int(row[26].strip())
                    position_counts["flatVenueRecords"] += 1
                    if len(row) > 26:
                        if row[21].strip() in {"芝", "ダート"}:
                            position_counts["flatVenueSurfaceAt21"] += 1
                        raw_dist = row[23].strip()
                        if (raw_dist.isascii() and raw_dist.isdecimal()
                                and 100 <= int(raw_dist) <= 5000):
                            position_counts["flatVenueDistanceAt23"] += 1
                        raw_starters = row[26].strip()
                        if (raw_starters.isascii() and raw_starters.isdecimal()
                                and 5 <= int(raw_starters) <= 18):
                            position_counts["flatVenueStartersAt26"] += 1
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
                "racelistPositionalSanityCounts": position_counts,
            })
    blank_reconciliation = {
        "racesWithBlank": 0, "blankHorseRows": 0,
        "blankHorseRowsWithTime": 0, "blankHorseRowsWithPopularity": 0,
        "blankRowsPerRaceHistogram": {},
        "declaredEqualsRanked": 0, "declaredEqualsAllHorselistRows": 0,
        "declaredEqualsNeither": 0,
        "rankedSubsetContiguous": 0, "rankedSubsetNoncontiguous": 0,
        "rankedSubsetDuplicateRanks": 0,
        "rankedSubsetHasRankOne": 0,
    }
    for key, profile in flat_rank_profiles.items():
        if not profile["blank"]:
            continue
        blank_reconciliation["racesWithBlank"] += 1
        blank_reconciliation["blankHorseRows"] += profile["blank"]
        blank_reconciliation["blankHorseRowsWithTime"] += profile["blankTime"]
        blank_reconciliation["blankHorseRowsWithPopularity"] += profile["blankPopularity"]
        count = str(profile["blank"])
        histogram = blank_reconciliation["blankRowsPerRaceHistogram"]
        histogram[count] = histogram.get(count, 0) + 1
        ranked = profile["ranked"]
        declared = flat_declared_counts.get(key)
        if declared == len(ranked):
            blank_reconciliation["declaredEqualsRanked"] += 1
        if declared == profile["all"]:
            blank_reconciliation["declaredEqualsAllHorselistRows"] += 1
        if declared not in (len(ranked), profile["all"]):
            blank_reconciliation["declaredEqualsNeither"] += 1
        if 1 in ranked:
            blank_reconciliation["rankedSubsetHasRankOne"] += 1
        if len(set(ranked)) != len(ranked):
            blank_reconciliation["rankedSubsetDuplicateRanks"] += 1
        if sorted(ranked) == list(range(1, len(ranked) + 1)):
            blank_reconciliation["rankedSubsetContiguous"] += 1
        else:
            blank_reconciliation["rankedSubsetNoncontiguous"] += 1
    other_integrity = {
        "flatRacesWithNonBlankDuplicateRanks": 0,
        "flatRacesWithNonBlankRankGaps": 0,
        "flatRacesWithMultiplePaybackRows": 0,
        "flatRacesWithIdenticalPaybackRows": 0,
        "flatRacesWithDistinctPaybackRows": 0,
        "flatRacesMissingPaybackRows": 0,
    }
    for key in flat_declared_counts:
        profile = flat_rank_profiles.get(key)
        if profile and not profile["blank"]:
            ranks = profile["ranked"]
            if len(ranks) != len(set(ranks)):
                other_integrity["flatRacesWithNonBlankDuplicateRanks"] += 1
            if sorted(ranks) != list(range(1, len(ranks) + 1)):
                other_integrity["flatRacesWithNonBlankRankGaps"] += 1
        rows = flat_payback_rows.get(key, [])
        if not rows:
            other_integrity["flatRacesMissingPaybackRows"] += 1
        if len(rows) > 1:
            other_integrity["flatRacesWithMultiplePaybackRows"] += 1
            if len(set(rows)) == 1:
                other_integrity["flatRacesWithIdenticalPaybackRows"] += 1
            else:
                other_integrity["flatRacesWithDistinctPaybackRows"] += 1
    return {
        "status": "NAR_LOCAL_HEADER_SHAPE_ONLY",
        "month": month,
        "members": aggregate,
        "flatOtherResultIntegrity": other_integrity,
        "flatFinishReconciliation": blank_reconciliation,
        "flatFinishRankAggregate": {
            "flatHorseRows": flat_horse_rows,
            "horseRowsByFixedCategory": dict(sorted(flat_finish_counts.items())),
            "flatRacesByExceptionalCategory": {
                name: len(keys) for name, keys in sorted(flat_finish_races.items())
            },
            "flatRacesWithExceptionalRank": len(
                set().union(*flat_finish_races.values()) if flat_finish_races else set()
            ),
            "rawRankTextExported": False,
        },
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
