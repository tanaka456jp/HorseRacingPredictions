"""No-network fictional NAR official interim odds ZIP contract tests."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
import csv
import importlib.util
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))
_SPEC = importlib.util.spec_from_file_location(
    "nar_interim_official_odds_test", _SCRIPTS / "capture_nar_official_daily_odds_preoff_once.py",
)
assert _SPEC is not None and _SPEC.loader is not None
S = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = S
_SPEC.loader.exec_module(S)

DAY = date(2026, 11, 10)
OBSERVED = datetime(2026, 11, 10, 0, 30, tzinfo=timezone.utc)
OFF = datetime(2026, 11, 10, 2, 35, tzinfo=timezone.utc)
SOURCE = datetime(2026, 11, 10, 0, 28, tzinfo=timezone.utc)
FILENAME = f"20261110_{int(SOURCE.timestamp())}_odds.zip"


def frozen_real_style() -> dict:
    return {
        "schema": "NAR.PC2.OfficialDailyForwardBaseline.v1",
        "day": DAY.isoformat(),
        "earliest_off_utc": OFF.isoformat().replace("+00:00", "Z"),
        "source_races": 2, "source_horses": 8,
        "odds_observed": False, "no_real_tickets": True,
        "complete_private_forecasts": [
            {"race_id": f"NAR:20261110:架空競馬場:{num:02d}",
             "scheduled_off_utc": OFF.isoformat(),
             "winner_scores": {str(h): float(6-h) for h in range(1,5)},
             "outsider_scores": {str(h): float(h) for h in range(1,5)},
             "top3": ["1", "2", "3"], "outsider": "4"}
            for num in (1, 2)
        ],
    }


def zip_odds(*, duplicate=False, bad_number=False, no_prices=False,
             date_error=False, unknown_race=False, wrong_zip_name=False):
    fields = ["競馬場", "競走年月日", "レース番号", "賭式",
              "番号1", "番号2", "番号3", "オッズ", "オッズ（最大）", "人気"]
    rows = []
    for race in (1, 2):
        for kind in ("単勝", "複勝"):
            for horse in range(1, 5):
                rows.append({
                    "競馬場": "架空競馬場",
                    "競走年月日": "20261109" if date_error else "20261110",
                    "レース番号": str(3 if unknown_race else race),
                    "賭式": kind, "番号1": "17" if bad_number else str(horse),
                    "番号2": "", "番号3": "",
                    "オッズ": "" if no_prices else "3.2",
                    "オッズ（最大）": "4.1" if kind == "複勝" and not no_prices else "",
                    "人気": str(horse),
                })
    rows.append({**rows[0], "賭式":"３連単", "番号1":"1",
                 "番号2":"2", "番号3":"3", "オッズ":"123.4"})
    if duplicate:
        rows.append(rows[0].copy())
    out = StringIO()
    csv.DictWriter(out, fieldnames=fields).writeheader()
    writer = csv.DictWriter(out, fieldnames=fields)
    writer.writerows(rows)
    sink = BytesIO()
    name = "wrong_name.csv" if wrong_zip_name else "20261110_odds.csv"
    with ZipFile(sink, "w") as z:
        z.writestr(name, out.getvalue().encode("utf-8-sig"))
    return sink.getvalue()


def evaluate(blob, *, source=FILENAME, captured=OBSERVED):
    return S.validate_private_official_odds_zip(
        blob, day=DAY, source_filename=source,
        captured_utc=captured, frozen=frozen_real_style(),
    )


def test_all_frozen_win_and_place_quotes_reconciled_without_selection_change():
    audit, private = evaluate(zip_odds())
    assert audit.registered_flat_races == 2
    assert audit.frozen_registered_horses == 8
    assert audit.market_rows == 17
    assert audit.win_rows == 8
    assert audit.place_rows == 8
    assert audit.in_scope_races_with_win_quote == 2
    assert audit.in_scope_races_with_place_quote == 2
    assert audit.planned_win_tickets_with_price == 2
    assert audit.planned_place_tickets_with_min_price == 2
    assert audit.planned_place_tickets_with_max_price == 2
    assert audit.planned_ticket_count == 4
    assert audit.minutes_before_first_scheduled_off > 10
    assert not audit.price_executable_at_order_time_verified
    assert not audit.after_cost_positive_ev_verified
    for item in private["selected_quotes_PRIVATE"]:
        assert item["frozen_win_horse_number"] == "1"
        assert item["frozen_place_horse_number"] == "4"
        assert item["win_interim_odds"] == "3.2"
        assert item["place_interim_odds_min"] == "3.2"
        assert item["place_interim_odds_max"] == "4.1"
        assert item["tickets_purchased"] is False


def test_missing_market_quote_never_becomes_zero_or_selected_race_exclusion():
    audit, private = evaluate(zip_odds(no_prices=True))
    assert audit.registered_flat_races == 2
    assert audit.planned_ticket_count == 4
    assert audit.planned_win_tickets_with_price == 0
    assert audit.planned_place_tickets_with_min_price == 0
    assert audit.missing_win_prices == 2
    assert audit.missing_place_min_prices == 2
    assert all(x["win_interim_odds"] is None for x in private["selected_quotes_PRIVATE"])


@pytest.mark.parametrize("kwargs", [
    {"duplicate": True},
    {"bad_number": True},
    {"date_error": True},
    {"unknown_race": True},
    {"wrong_zip_name": True},
])
def test_odds_zip_rejects_untrusted_or_inconsistent_official_fixture(kwargs):
    with pytest.raises(S.NarPreoffDailyHold):
        evaluate(zip_odds(**kwargs))


def test_source_clock_must_not_be_after_download_or_stale():
    source_old = datetime(2026, 11, 9, 23, 40, tzinfo=timezone.utc)
    with pytest.raises(S.NarPreoffDailyHold, match="STALE"):
        evaluate(zip_odds(), source=f"20261110_{int(source_old.timestamp())}_odds.zip")
    source_future = OBSERVED + timedelta(minutes=4)
    with pytest.raises(S.NarPreoffDailyHold, match="STALE"):
        evaluate(zip_odds(), source=f"20261110_{int(source_future.timestamp())}_odds.zip")


def test_never_accept_first_off_already_close_or_past():
    with pytest.raises(S.NarPreoffDailyHold, match="TOO_LATE"):
        evaluate(zip_odds(), captured=OFF-timedelta(minutes=7))


def test_zip_untrusted_or_wrong_day_is_rejected():
    with pytest.raises(S.NarPreoffDailyHold):
        evaluate(b"fake archive")
    with pytest.raises(S.NarPreoffDailyHold):
        evaluate(zip_odds(), source="20261109_1790000000_odds.zip")


def test_direct_capture_has_no_extra_credential_or_unbounded_polling():
    assert S._OFFICIAL_ODDS_URL == (
        "https://www.keiba.go.jp/KeibaWeb/DataDownload/OddsDataDownload?type=daily"
    )
    assert S._MAX_SNAPSHOTS_PER_DAY <= 6
    assert S._MIN_REQUEST_GAP.total_seconds() >= 120
