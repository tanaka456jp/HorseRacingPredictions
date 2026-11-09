"""Network-free fictional NAR daily preoff ZIP tests; never fetch real NAR."""
from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile
import csv
import importlib.util
import sys

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "capture_nar_official_daily_preoff_once.py"
_SPEC = importlib.util.spec_from_file_location("nar_official_daily_preoff_test", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
M = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = M
_SPEC.loader.exec_module(M)
DAY = date(2026, 11, 10)
EARLY = datetime(2026, 11, 10, 0, 0, tzinfo=timezone.utc)


def _csv(rows):
    io = StringIO()
    writer = csv.DictWriter(io, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return io.getvalue().encode("utf-8-sig")


def fictional_daily_zip(*, result=False, incomplete=False,
                        wrong_day=False, post_race=False, nested=False):
    ymd = "20261111" if wrong_day else "20261110"
    races = [{
        "競馬場": "架空地方場", "競走年月日": ymd,
        "レース番号": "1", "発走時刻": "1135", "頭数": "4",
        "上がり3F": "38.5" if post_race else "",
    }, {
        "競馬場": "架空地方場", "競走年月日": ymd,
        "レース番号": "2", "発走時刻": "1210", "頭数": "4",
        "上がり3F": "",
    }]
    horses = [{
        "競馬場": "架空地方場", "競走年月日": ymd,
        "レース番号": str(race), "馬番": str(number),
        "馬名": f"架空馬{race}-{number}",
        "着順": "1" if result and race == 1 and number == 1 else "",
        "タイム": "", "着差": "", "上がり3F": "",
    } for race in (1, 2) for number in range(1, 5)]
    if incomplete:
        horses.pop()
    io = BytesIO()
    with ZipFile(io, "w") as package:
        prefix = "../" if nested else ""
        package.writestr(prefix + "20261110_racelist.csv", _csv(races))
        package.writestr("20261110_horselist.csv", _csv(horses))
    return io.getvalue()


def test_official_daily_preoff_accepts_complete_fictional_future_roster():
    audit = M.validate_official_daily_race_zip(
        fictional_daily_zip(), race_day=DAY, host_captured_utc=EARLY,
    )
    assert audit.flat_races == 2
    assert audit.registered_horses == 8
    assert audit.earliest_off_utc == "2026-11-10T02:35:00Z"
    assert audit.min_lead_seconds > 0
    assert not audit.host_clock_independently_attested
    assert not audit.before_off_forecast_exists
    assert not audit.positive_expected_value_demonstrated


@pytest.mark.parametrize("kwargs", [
    {"result": True}, {"incomplete": True}, {"wrong_day": True},
    {"post_race": True}, {"nested": True},
])
def test_official_daily_preoff_fails_closed_on_synthetic_source_contamination(kwargs):
    with pytest.raises(M.NarPreoffDailyHold):
        M.validate_official_daily_race_zip(
            fictional_daily_zip(**kwargs), race_day=DAY,
            host_captured_utc=EARLY,
        )


def test_official_daily_preoff_blocks_late_snapshot_and_untrustworthy_clock():
    with pytest.raises(M.NarPreoffDailyHold, match="NOT_EARLY_ENOUGH"):
        M.validate_official_daily_race_zip(
            fictional_daily_zip(), race_day=DAY,
            host_captured_utc=datetime(
                2026, 11, 10, 2, 30, tzinfo=timezone.utc,
            ),
        )
    with pytest.raises(M.NarPreoffDailyHold, match="CURRENT_JST_DAY_REQUIRED"):
        M.validate_official_daily_race_zip(
            fictional_daily_zip(), race_day=DAY,
            host_captured_utc=datetime(
                2026, 11, 9, 12, 0, tzinfo=timezone.utc,
            ),
        )
    with pytest.raises(M.NarPreoffDailyHold):
        M.validate_official_daily_race_zip(
            fictional_daily_zip(), race_day=DAY,
            host_captured_utc=datetime(2026, 11, 10, 0, 0),
        )


def test_official_daily_preoff_rejects_arbitrary_bytes():
    with pytest.raises(M.NarPreoffDailyHold):
        M.validate_official_daily_race_zip(
            b"NOT A ZIP", race_day=DAY, host_captured_utc=EARLY,
        )
