"""Fictional source-only test of manual NAR race ZIP -> freeze compatibility."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
import import_nar_manual_daily_race_offline as M  # noqa: E402
from test_nar_official_daily_preoff import fictional_daily_zip, F  # noqa: E402
from capture_nar_official_daily_odds_preoff_once import (  # noqa: E402
    _load_original_frozen_forecast,
)
from capture_nar_official_daily_preoff_once import NarPreoffDailyHold  # noqa: E402

NOW=datetime(2026,11,10,0,0,tzinfo=timezone.utc)


def _setup(tmp_path,monkeypatch,*,kwargs=None):
    inbox=tmp_path / "manual-race-inbox"
    inbox.mkdir()
    name=f"20261110_{int(NOW.timestamp())}_race.zip"
    path=inbox/name
    path.write_bytes(fictional_daily_zip(**(kwargs or {})))
    monkeypatch.setattr(M,"_now_utc",lambda:NOW)
    return path


def test_manual_source_full_forecast_freeze_works_without_NAR_HTTP(
    tmp_path,monkeypatch,
):
    path=_setup(tmp_path,monkeypatch)
    import urllib.request
    monkeypatch.setattr(urllib.request,"urlopen",
                        lambda *a,**k: (_ for _ in ()).throw(
                            AssertionError("Must not fetch NAR")))
    a=M.import_user_downloaded_preoff_race(tmp_path,path)
    assert a.flat_races==2
    assert a.registered_horses==8
    assert a.min_lead_seconds>600
    originals=list(tmp_path.glob("20261110_????????T??????Z_race.zip"))
    assert len(originals)==1
    original=originals[0]
    assert original.read_bytes()==path.read_bytes()
    meta=json.loads(original.with_name(original.name.replace(
        "_race.zip","_private_provenance.json"
    )).read_text(encoding="utf-8"))
    assert meta["source_input_mode"]=="USER_DOWNLOADED_OFFLINE"
    assert meta["automated_nar_requests"]==0
    assert meta["independent_preoff_attestation"] is False
    snapshot,digest=F.prepare_private_daily_baseline(
        original.read_bytes(),observed_at_utc=NOW,
        generated_at_utc=NOW+timedelta(minutes=1),
        race_day=NOW.astimezone(M._JST).date(),
        private_salt=bytes(range(32)),
    )
    (tmp_path/"20261110_baseline_forecast_PRIVATE.json").write_text(
        json.dumps(snapshot),encoding="utf-8",
    )
    recovered,zipbytes=_load_original_frozen_forecast(
        tmp_path, NOW.astimezone(M._JST).date(),
    )
    assert recovered==snapshot
    assert zipbytes==path.read_bytes()
    assert len(digest)==64
    assert recovered["no_real_tickets"] is True


def test_duplicate_manual_preoff_source_cannot_replace_frozen_original(
    tmp_path,monkeypatch
):
    p=_setup(tmp_path,monkeypatch)
    M.import_user_downloaded_preoff_race(tmp_path,p)
    with pytest.raises(NarPreoffDailyHold,match="PRIOR_SOURCE_EXISTS"):
        M.import_user_downloaded_preoff_race(tmp_path,p)


def test_late_user_manual_race_source_is_rejected_without_private_copy(
    tmp_path,monkeypatch
):
    p=_setup(tmp_path,monkeypatch)
    monkeypatch.setattr(M,"_now_utc",
                        lambda: datetime(2026,11,10,2,30,tzinfo=timezone.utc))
    with pytest.raises(NarPreoffDailyHold,match="NOT_EARLY_ENOUGH"):
        M.import_user_downloaded_preoff_race(tmp_path,p)
    assert not list(tmp_path.glob("20261110_????????T??????Z_race.zip"))


def test_manual_race_after_result_or_incomplete_roster_is_rejected(
    tmp_path,monkeypatch
):
    for item in ({"result":True},{"post_race":True},{"incomplete":True}):
        location=tmp_path/("case"+str(len(list(tmp_path.iterdir()))))
        location.mkdir()
        p=_setup(location,monkeypatch,kwargs=item)
        with pytest.raises(NarPreoffDailyHold):
            M.import_user_downloaded_preoff_race(location,p)


def test_wrong_path_and_future_generated_zip_hold(tmp_path,monkeypatch):
    p=_setup(tmp_path,monkeypatch)
    outside=tmp_path/p.name
    outside.write_bytes(p.read_bytes())
    with pytest.raises(NarPreoffDailyHold,match="INBOX_ONLY"):
        M.import_user_downloaded_preoff_race(tmp_path,outside)
    future=NOW+timedelta(minutes=5)
    new=p.with_name(f"20261110_{int(future.timestamp())}_race.zip")
    new.write_bytes(p.read_bytes())
    with pytest.raises(NarPreoffDailyHold,match="SOURCE_TIME_INVALID"):
        M.import_user_downloaded_preoff_race(tmp_path,new)
