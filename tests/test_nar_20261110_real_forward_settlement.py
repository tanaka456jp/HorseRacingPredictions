"""Synthetic-only full-day prospective official-settlement gate checks; no NAR download."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import csv
import importlib.util
from io import BytesIO, StringIO
from pathlib import Path
import sys
from zipfile import ZipFile
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
_MODULE = importlib.util.spec_from_file_location(
    "nar_real_forward_settlement_unit_test",
    _ROOT / "scripts" / "reconcile_nar_20261110_forward_official_results.py",
)
assert _MODULE is not None and _MODULE.loader is not None
S = importlib.util.module_from_spec(_MODULE)
sys.modules[_MODULE.name] = S
_MODULE.loader.exec_module(S)
_LAST_OFF = datetime(2026, 11, 10, 2, 0, tzinfo=timezone.utc)
_OBS = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
_SOURCE = datetime(2026, 11, 10, 11, 58, tzinfo=timezone.utc)
_SOURCE_NAME = f"20261110_{int(_SOURCE.timestamp())}_race.zip"


def _csv(rows):
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def _zip(items):
    sink = BytesIO()
    with ZipFile(sink, "w") as z:
        for name, rows in items.items():
            z.writestr(f"20261110_{name}.csv", _csv(rows))
    return sink.getvalue()


def synthetic_full_day(*, missing_result=False, scratch=False,
                       duplicate_race=False, unexpected_race=False):
    races, horses_old, horses_final, pays, forecasts = [], [], [], [], []
    for r in range(59):
        track = f"架空場{r//20+1}"
        no = r % 20 + 1
        name = f"NAR:20261110:{track}:{no:02d}"
        num = 11 if r < 51 else 10
        race = {
            "競馬場":track, "競走年月日":"20261110",
            "レース番号":str(no), "頭数":str(num),
        }
        races.append(race)
        wins = {str(h):float(num+1-h) for h in range(1,num+1)}
        podium = {str(h):float(num+1-h) for h in range(1,num+1)}
        for h in range(1,num+1):
            row = {
                "競馬場":track, "競走年月日":"20261110",
                "レース番号":str(no), "馬番":str(h),
                "馬名":f"架空馬{r}-{h}",
            }
            horses_old.append(row)
            horses_final.append({
                **row, "着順":"" if scratch and r==0 and h==4 else str(h),
                "着差":"取消" if scratch and r==0 and h==4 else "",
            })
        pays.append({
            "競馬場":track, "競走年月日":"20261110",
            "レース番号":str(no), "単勝組番":"1",
            "単勝払戻金（円）":"220",
            "複勝組番1":"1", "複勝払戻金1（円）":"110",
            "複勝組番2":"2", "複勝払戻金2（円）":"120",
            "複勝組番3":"3", "複勝払戻金3（円）":"150",
        })
        forecasts.append({
            "race_id":name,
            "scheduled_off_utc":_LAST_OFF.isoformat(),
            "top3":["1","2","3"],
            "outsider":"4",
            "winner_scores":wins,
        })
    if missing_result:
        pays.pop()
    if duplicate_race:
        races.append(races[0].copy())
    if unexpected_race:
        pays.append({**pays[0],"競馬場":"架空場4"})  # Truly outside original 59-race calendar.
    frozen = {
        "schema":"NAR.PC2.OfficialDailyForwardBaseline.v1",
        "day":"2026-11-10", "source_races":59, "source_horses":641,
        "no_real_tickets":True, "odds_observed":False,
        "complete_private_forecasts":forecasts,
    }
    before = _zip({"horselist":horses_old})
    after = _zip({"racelist":races,"horselist":horses_final,"payback":pays})
    return frozen,before,after


def test_all_59_fictional_races_hypothetical_positive_still_no_ev():
    frozen,prior,post = synthetic_full_day()
    a = S.verify_real_forward_final_results(
        frozen,prior,post,result_source_name=_SOURCE_NAME,
        observed_utc=_OBS,
    )
    assert a.frozen_flat_races == 59
    assert a.frozen_horses == 641
    assert a.official_result_horses == 641
    assert a.official_result_races == 59
    assert a.official_payback_races == 59
    assert a.unresolved_races == 0
    assert a.hypothetical_full_day_win_stake_yen == 5900
    assert a.hypothetical_full_day_place_stake_yen == 5900
    assert a.hypothetical_full_day_gross_return_yen == 59*220
    assert a.hypothetical_full_day_net_yen == 59*20
    assert a.hypothetical_full_day_roi == pytest.approx(0.10)
    assert not a.contemporaneous_quoted_prices_verified
    assert not a.real_tickets_purchased
    assert not a.after_cost_positive_ev_proven


@pytest.mark.parametrize("kwargs",[
    {"missing_result":True},
    {"scratch":True},
])
def test_missing_payout_or_scratched_horse_never_cherrypicks_subset_roi(kwargs):
    frozen,prior,post=synthetic_full_day(**kwargs)
    a=S.verify_real_forward_final_results(
        frozen,prior,post,result_source_name=_SOURCE_NAME,
        observed_utc=_OBS,
    )
    assert a.frozen_flat_races == 59
    assert a.unresolved_races >= 1
    assert a.fully_interpretable_races < 59
    assert a.hypothetical_full_day_roi is None
    assert a.hypothetical_full_day_net_yen is None
    assert a.hypothetical_full_day_gross_return_yen is None
    assert not a.after_cost_positive_ev_proven


@pytest.mark.parametrize("kwargs",[
    {"duplicate_race":True},
    {"unexpected_race":True},
])
def test_duplicate_or_unfrozen_race_not_silently_selected(kwargs):
    frozen,prior,post=synthetic_full_day(**kwargs)
    with pytest.raises(S.NarPreoffDailyHold):
        S.verify_real_forward_final_results(
            frozen,prior,post,result_source_name=_SOURCE_NAME,
            observed_utc=_OBS,
        )


def test_after_off_and_official_timestamp_must_precede_paper_settlement():
    frozen,prior,post=synthetic_full_day()
    early= datetime(2026,11,10,1,30,tzinfo=timezone.utc)
    with pytest.raises(S.NarPreoffDailyHold,match="LAST_OFF_NOT_FINISHED"):
        S.verify_real_forward_final_results(
            frozen,prior,post,
            result_source_name=f"20261110_{int(early.timestamp())}_race.zip",
            observed_utc=early+timedelta(minutes=2),
        )
    stale= _OBS-timedelta(hours=1)
    with pytest.raises(S.NarPreoffDailyHold,match="STALE_SOURCE_TIME"):
        S.verify_real_forward_final_results(
            frozen,prior,post,
            result_source_name=f"20261110_{int(stale.timestamp())}_race.zip",
            observed_utc=_OBS,
        )


def test_2023_2024_or_2025_2026_sealed_historical_data_cannot_replace_frozen_day():
    frozen,prior,post=synthetic_full_day()
    frozen["day"]="2026-11-09"
    with pytest.raises(S.NarPreoffDailyHold):
        S.verify_real_forward_final_results(
            frozen,prior,post,result_source_name=_SOURCE_NAME,
            observed_utc=_OBS,
        )
