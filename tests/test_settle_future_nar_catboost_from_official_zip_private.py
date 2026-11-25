"""Entirely fictional NAR final ZIP: validate ALL frozen races, no cherry-pick."""
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO, StringIO
import csv
import json
from pathlib import Path
import sys
from zipfile import ZipFile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
sys.path.insert(0,str(ROOT/"tests"))
import settle_future_nar_catboost_from_official_zip_private as M  # noqa: E402
import freeze_nar_partial_catboost_daily_private as F  # noqa: E402
from test_nar_official_daily_preoff import fictional_daily_zip  # noqa: E402
from test_freeze_nar_partial_catboost_daily_private import fake_model  # noqa: E402

DAY=date(2026,11,10)
OBS=datetime(2026,11,10,0,tzinfo=timezone.utc)
GEN=OBS+timedelta(minutes=2)
LAST=datetime(2026,11,10,3,10,tzinfo=timezone.utc)
RELEASE=LAST+timedelta(minutes=25)
RECEIVED=RELEASE+timedelta(minutes=3)


def _csv(rows):
    io=StringIO()
    w=csv.DictWriter(io,fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return io.getvalue().encode("utf-8-sig")


def completed_zip(*, scratch=False, payout_mismatch=False, dnf=False, dead_heat=False, invalid_tie=False):
    ymd="20261110"
    races=[{"競馬場":"架空地方場","競走年月日":ymd,
            "レース番号":str(r),"頭数":"4"}
           for r in (1,2)]
    horses=[]
    for r in (1,2):
        for h in range(1,5):
            rank=str(h)
            if scratch and r==2 and h==4:
                rank="取消"
            if dnf and r==2 and h==4:
                rank="競走中止"
            if (dead_heat or invalid_tie) and r==2 and h==2:
                rank="1"
            if invalid_tie and r==2 and h==3:
                rank="2"
            horses.append({
                "競馬場":"架空地方場","競走年月日":ymd,
                "レース番号":str(r),"馬番":str(h),
                "馬名":f"架空馬{r}-{h}", "着順":rank,
            })
    payouts=[{
        "競馬場":"架空地方場","競走年月日":ymd,
        "レース番号":str(r),"単勝組番":("4" if payout_mismatch else "1"),
        "単勝払戻金（円）":str(200+r*100),
    } for r in (1,2)]
    if dead_heat or invalid_tie:
        payouts.append({"競馬場":"架空地方場","競走年月日":ymd,
                        "レース番号":"2","単勝組番":"2","単勝払戻金（円）":"190"})
    out=BytesIO()
    with ZipFile(out,"w") as z:
        z.writestr(ymd+"_racelist.csv",_csv(races))
        z.writestr(ymd+"_horselist.csv",_csv(horses))
        z.writestr(ymd+"_payback.csv",_csv(payouts))
    return out.getvalue()


def prepared(tmp_path,monkeypatch):
    monkeypatch.setenv("COMPUTERNAME","DESKTOP-MVV1FD4")
    folder=tmp_path/"nar-prospective-captures"
    folder.mkdir()
    inbox=folder/"postevent-inbox"
    inbox.mkdir()
    original=fictional_daily_zip()
    source=folder/"20261110_20261110T000000Z_race.zip"
    source.write_bytes(original)
    salt=bytes(range(32))
    sidecar={
        "schema":"NAR.OfficialDailyPreoffCapture.v1",
        "host_captured_utc":OBS.isoformat(),
        "salt_hex_PRIVATE":salt.hex(),
        "salted_zip_sha256_PRIVATE":sha256(
            b"NAR_OFFICIAL_DAILY_RACE_V1\x00"+salt+original
        ).hexdigest(),
    }
    (folder/source.name.replace("_race.zip","_private_provenance.json")).write_text(
        json.dumps(sidecar),encoding="utf-8")
    monkeypatch.setattr(F,"load_nar_private_dual_candidate",lambda _:fake_model())
    F.freeze_private_from_saved_daily(tmp_path,generated_utc=GEN)
    p=inbox/f"20261110_{int(RELEASE.timestamp())}_race.zip"
    p.write_bytes(completed_zip())
    return p


def test_full_day_actual_model_official_paper_hits_and_roi(tmp_path,monkeypatch):
    final=prepared(tmp_path,monkeypatch)
    output=M.score_private_postevent_zip(tmp_path,final,now_utc=RECEIVED)
    assert output["status"].startswith("COMPLETE_DESCRIPTIVE")
    assert output["frozen_race_denominator"]==2
    assert output["top1_win_hits"]==2
    assert output["top1_win_hit_rate"]==1.0
    assert output["hypothetical_100_yen_win_stake"]==200
    assert output["hypothetical_official_return_yen"]==700
    assert output["hypothetical_net_paper_roi"]==2.5
    assert output["three_of_five_feature_ablation"]
    assert not output["independent_prediction_receipt_checked"]
    assert not output["positive_ev_proven"]
    assert not output["private_files_modified"]


@pytest.mark.parametrize("issue",["scratch","payout","late","missing"])
def test_selected_winner_and_full_denominator_errors_hold_without_roi(
    tmp_path,monkeypatch,issue,
):
    final=prepared(tmp_path,monkeypatch)
    if issue in ("scratch","payout"):
        final.write_bytes(completed_zip(
            scratch=issue=="scratch", payout_mismatch=issue=="payout",
        ))
    if issue=="missing":
        final.unlink()
        final=tmp_path/"nar-prospective-captures"/"postevent-inbox"/"bad.zip"
        final.write_bytes(completed_zip())
    with pytest.raises(Exception):
        M.score_private_postevent_zip(
            tmp_path,final,
            now_utc=LAST+timedelta(minutes=10) if issue=="late" else RECEIVED,
        )


def test_frozen_model_tampering_never_enters_official_settlement(tmp_path,monkeypatch):
    final=prepared(tmp_path,monkeypatch)
    snap=tmp_path/"nar-prospective-captures"/"20261110_NAR_partial3of5_dual_catboost_PRIVATE.json"
    doc=json.loads(snap.read_text(encoding="utf-8"))
    doc["frozen_shadow_PRIVATE"]["races"][0]["top3"][0]="4"
    snap.write_text(json.dumps(doc),encoding="utf-8")
    with pytest.raises(ValueError,match="COMMITMENT"):
        M.score_private_postevent_zip(tmp_path,final,now_utc=RECEIVED)


@pytest.mark.parametrize("kind", ["dnf", "dead_heat"])
def test_resolved_exception_keeps_all_races(tmp_path, monkeypatch, kind):
    final=prepared(tmp_path,monkeypatch)
    final.write_bytes(completed_zip(**{kind: True}))
    result=M.score_private_postevent_zip(tmp_path,final,now_utc=RECEIVED)
    assert result["fully_settled_races"]==2
    assert result["ordinary_fully_settled_races"]==1
    assert result["races_with_explicit_dnf"]==int(kind=="dnf")
    assert result["races_with_numeric_dead_heat"]==int(kind=="dead_heat")
    assert result["hypothetical_100_yen_win_stake"]==200
    assert result["hypothetical_official_return_yen"]==700
    assert not result["positive_ev_proven"]


def test_invalid_rank_tie_still_holds(tmp_path, monkeypatch):
    final=prepared(tmp_path,monkeypatch)
    final.write_bytes(completed_zip(invalid_tie=True))
    with pytest.raises(M.PrivateNarSettlementHold, match="UNRESOLVED_FINISH"):
        M.score_private_postevent_zip(tmp_path,final,now_utc=RECEIVED)
