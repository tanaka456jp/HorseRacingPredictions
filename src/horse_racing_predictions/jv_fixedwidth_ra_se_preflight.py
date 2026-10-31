"""CP932 RA/SE fixed-width layout check, no raw data persistence.

JRA-VAN record layouts RA >= 1270 bytes, SE >= 553 bytes. Checks only
bytewise structural fields in memory. No horse names, date values, result
labels, odds, licence keys or source text are returned or logged.
This is *not* a substitute for independently licensed historical training.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JvFixedWidthCheck:
    record_type: str
    length_valid: bool
    header_valid: bool
    jra_course_code_valid: bool
    date_shape_valid: bool
    codepage_roundtrip_valid: bool


_LENGTH = {"RA": 1270, "SE": 553}
_JRA_COURSE_CODES = frozenset(f"{c:02d}" for c in range(1, 11))


def verify_ra_se_fixed_width(record_type: str, text: str) -> JvFixedWidthCheck:
    """No raw field values escape this validator; returns booleans only."""
    if record_type not in _LENGTH:
        raise ValueError("only RA/SE can be checked")
    if not isinstance(text, str):
        raise ValueError("decoded record text required")
    try:
        raw = text.encode("cp932", errors="strict")
    except UnicodeEncodeError:
        return JvFixedWidthCheck(
            record_type, False, False, False, False, False,
        )
    length_ok = len(raw) >= _LENGTH[record_type]
    # Official JV-Data offsets are one-based in interface documentation.
    header_ok = (
        len(raw) >= 27 and raw[0:2] == record_type.encode("ascii")
        and chr(raw[2]).isalnum()
    )
    year = raw[11:15]
    month_day = raw[15:19]
    place = raw[19:21]
    meet_day_race = raw[21:27]
    date_ok = (
        len(year) == 4 and year.isdigit()
        and len(month_day) == 4 and month_day.isdigit()
        and 1 <= int(month_day[0:2]) <= 12
        and 1 <= int(month_day[2:4]) <= 31
        and meet_day_race.isdigit()
    )
    course_ok = (
        len(place) == 2
        and place.decode("ascii", errors="replace") in _JRA_COURSE_CODES
    )
    return JvFixedWidthCheck(
        record_type=record_type,
        length_valid=length_ok,
        header_valid=header_ok,
        jra_course_code_valid=course_ok,
        date_shape_valid=date_ok,
        codepage_roundtrip_valid=True,
    )
