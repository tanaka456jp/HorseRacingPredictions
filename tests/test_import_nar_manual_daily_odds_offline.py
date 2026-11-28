"""Synthetic-only local NAR manual odds reader. Never calls the web."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from io import BytesIO, StringIO
import csv
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import import_nar_manual_daily_odds_offline as M  # noqa: E402
from capture_nar_official_daily_preoff_once import NarPreoffDailyHold  # noqa: E402

NOW = datetime(2026, 11, 19, 1, 0, tzinfo=timezone.utc)
DAY = date(2026, 11, 19)
SOURCE = NOW - timedelta(minutes=2)
OFF1 = NOW + timedelta(hours=1)
OFF2 = NOW + timedelta(hours=4)


def _archive(*, empty_market=False, missing_win_prices=False) -> bytes:
    names = ["競馬場", "競走年月日", "レース番号", "賭式",
             "番号1", "番号2", "番号3", "オッズ", "オッズ（最大）", "人気"]
    text = StringIO()
    wr = csv.DictWriter(text, fieldnames=names)
    wr.writeheader()
    for r in (() if empty_market else (1, 2)):
        for kind in ("単勝", "複勝"):
            for h in (1, 2, 3, 4):
                wr.writerow({
                    "競馬場": "架空場", "競走年月日": "20261119",
                    "レース番号":str(r), "賭式":kind,
                    "番号1":str(h), "番号2":"", "番号3":"",
                    "オッズ":"" if missing_win_prices and kind=="単勝" else "2.5",
                    "オッズ（最大）":"3.1" if kind=="複勝" else "",
                    "人気":str(h),
                })
    sink = BytesIO()
    with ZipFile(sink, "w") as z:
        z.writestr("20261119_odds.csv", text.getvalue().encode("utf-8-sig"))
    return sink.getvalue()


def _frozen():
    return {
        "schema":"NAR.PC2.OfficialDailyForwardBaseline.v1",
        "day":DAY.isoformat(), "source_races":2, "source_horses":8,
        "earliest_off_utc":OFF1.isoformat(),
        "odds_observed":False,"no_real_tickets":True,
        "commitment_digest":"a"*64,
        "complete_private_forecasts":[
            {"race_id":f"NAR:20261119:架空場:{i:02d}",
             "scheduled_off_utc":scheduled.isoformat(),
             "top3":["1","2","3"],"outsider":"4",
             "winner_scores":{str(h):float(h) for h in range(1,5)}}
            for i,scheduled in ((1,OFF1),(2,OFF2))
        ],
    }


def _setup(tmp_path,monkeypatch,*,archive=None):
    inbox=tmp_path / "manual-odds-inbox"
    inbox.mkdir()
    filename=f"20261119_{int(SOURCE.timestamp())}_odds.zip"
    path=inbox / filename
    path.write_bytes(_archive() if archive is None else archive)
    monkeypatch.setattr(M,"_now_utc",lambda:NOW)
    monkeypatch.setattr(M,"_load_original_frozen_forecast",
                        lambda folder,day:(_frozen(), b"FICTIONAL ONLY"))
    return path


def test_user_provided_zip_can_be_audited_without_any_provider_connection(
    tmp_path,monkeypatch
):
    candidate=_setup(tmp_path,monkeypatch)
    import urllib.request
    def fail(*a,**kw):
        raise AssertionError("NO PROVIDER REQUESTS ALLOWED")
    monkeypatch.setattr(urllib.request,"urlopen",fail)
    a=M.import_user_downloaded_daily_odds(tmp_path,candidate)
    assert a.registered_flat_races==2
    assert a.planned_ticket_count==4
    assert a.planned_win_tickets_with_price==2
    assert a.planned_place_tickets_with_min_price==2
    assert a.after_cutoff_raw_quote_rows_ignored==0
    sidecar=tmp_path / candidate.name.replace(
        "_odds.zip", "_manually_downloaded_odds_PRIVATE.json"
    )
    private=json.loads(sidecar.read_text(encoding="utf-8"))
    assert private["download_mode"]=="USER_SUPPLIED_OFFLINE_NO_PROVIDER_REQUEST"
    assert private["individual_authorized_automated_polling"] is False
    assert private["independent_hosted_receipt_verified"] is False
    assert private["actual_order_execution_verified"] is False
    assert private["source_uploaded"] is False
    assert candidate.read_bytes()==_archive()
    assert len(private["quotes_PRIVATE"]["selected_quotes_PRIVATE"])==2


def test_reimport_cannot_overwrite_original_or_sidecar(tmp_path,monkeypatch):
    path=_setup(tmp_path,monkeypatch)
    M.import_user_downloaded_daily_odds(tmp_path,path)
    before=path.read_bytes()
    with pytest.raises(NarPreoffDailyHold,match="ALREADY_IMPORTED"):
        M.import_user_downloaded_daily_odds(tmp_path,path)
    assert path.read_bytes()==before


def test_offline_inbox_rejects_outside_files_and_wrong_day(
    tmp_path,monkeypatch
):
    path=_setup(tmp_path,monkeypatch)
    outside=tmp_path / path.name
    outside.write_bytes(path.read_bytes())
    with pytest.raises(NarPreoffDailyHold,match="INBOX_ONLY"):
        M.import_user_downloaded_daily_odds(tmp_path,outside)
    wrong=path.with_name("20261118_1790000000_odds.zip")
    wrong.write_bytes(path.read_bytes())
    with pytest.raises(NarPreoffDailyHold,match="WRONG_DAY"):
        M.import_user_downloaded_daily_odds(tmp_path,wrong)


def test_offline_rejects_post_off_receipt_despite_nonempty_source(
    tmp_path,monkeypatch
):
    path=_setup(tmp_path,monkeypatch)
    monkeypatch.setattr(M,"_now_utc",lambda:OFF2+timedelta(minutes=1))
    with pytest.raises(NarPreoffDailyHold,match="STALE|TOO_LATE"):
        M.import_user_downloaded_daily_odds(tmp_path,path)
    assert not (tmp_path / path.name.replace(
        "_odds.zip", "_manually_downloaded_odds_PRIVATE.json"
    )).exists()


def test_offline_rejects_forged_future_source(tmp_path,monkeypatch):
    path=_setup(tmp_path,monkeypatch)
    future=NOW+timedelta(minutes=4)
    fabricated=path.with_name(
        f"20261119_{int(future.timestamp())}_odds.zip"
    )
    fabricated.write_bytes(path.read_bytes())
    with pytest.raises(NarPreoffDailyHold,match="STALE|FUTURE"):
        M.import_user_downloaded_daily_odds(tmp_path,fabricated)


def test_post_first_off_later_race_quote_only_with_frozen_denominator(
    tmp_path,monkeypatch
):
    path=_setup(tmp_path,monkeypatch)
    after_first=OFF1+timedelta(minutes=15)
    revised=path.with_name(
        f"20261119_{int((after_first-timedelta(seconds=30)).timestamp())}_odds.zip"
    )
    revised.write_bytes(path.read_bytes())
    monkeypatch.setattr(M,"_now_utc",lambda:after_first)
    a=M.import_user_downloaded_daily_odds(tmp_path,revised)
    assert a.registered_flat_races==2
    assert a.future_preoff_eligible_races==1
    assert a.past_or_closed_races==1
    assert a.missing_win_prices==1
    assert a.missing_place_min_prices==1
    assert a.after_cutoff_raw_quote_rows_ignored==8


@pytest.mark.parametrize("mode,expected_status,expected_exit", [
    ("market_empty", "HOLD_MANUAL_OFFLINE_CSV_NO_MARKET_ROWS", 2),
    ("place_only", "HOLD_MANUAL_OFFLINE_NO_SELECTED_WIN_QUOTES", 2),
    ("win_quotes", "PRIVATE_OFFLINE_WIN_QUOTES_SEEN_INDICATIVE_ONLY", 0),
])
def test_manual_offline_cli_never_reports_win_readiness_without_win_prices(
    tmp_path, monkeypatch, capsys, mode, expected_status, expected_exit,
):
    """Source preservation is not the same as usable preoff WIN evidence."""
    kwargs = {
        "empty_market": mode == "market_empty",
        "missing_win_prices": mode == "place_only",
    }
    candidate = _setup(tmp_path, monkeypatch, archive=_archive(**kwargs))
    monkeypatch.setattr(sys, "argv", [
        "import_nar_manual_daily_odds_offline.py",
        "--private-capture-dir", str(tmp_path),
    ])
    assert M.main() == expected_exit
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == expected_status
    assert output["source_market_rows"] == (0 if mode == "market_empty" else 16)
    assert output["quoted_selected_win"] == (2 if mode == "win_quotes" else 0)
    assert output["provider_network_requests"] == 0
    assert output["private_source_uploaded"] is False
    assert output["positive_ev_proven"] is False
    assert candidate.read_bytes() == _archive(**kwargs)
    # Immutable local source preserved even when its research audit is HOLD.
    assert (tmp_path / candidate.name.replace(
        "_odds.zip", "_manually_downloaded_odds_PRIVATE.json"
    )).exists()
