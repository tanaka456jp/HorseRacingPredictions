"""Native JRA two-model source-to-immutable forecast regression, fictional only."""
from datetime import datetime, timedelta
from hashlib import sha256
import json
import sys
from pathlib import Path

import pytest

from horse_racing_predictions.dual_candidate_private_preview import load_dual_research_candidate
from horse_racing_predictions.jra_future_shadow_features import prepare_jra_future_shadow_features
from test_dual_candidate_private_preview import _artifact, _fake_recent_and_entries
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from freeze_prospective_dual_catboost_private import freeze_private_future

NOW = datetime.fromisoformat("2026-11-01T07:00:00+09:00")


def test_native_jra_numbered_source_to_frozen_full_card(tmp_path, monkeypatch):
    candidate = _artifact(tmp_path)
    native = load_dual_research_candidate(candidate)
    history, entries, ids = _fake_recent_and_entries()
    counts = {rid: 6 for rid in ids}
    calendar = {
        "schema": "HorseRacing.PrivateFutureCalendar.v1",
        "jurisdiction": "JRA", "race_day_jst": "2026-11-01",
        "source_asof_utc": NOW.isoformat(),
        "scheduled_off_utc": {rid: (NOW+timedelta(hours=3)).isoformat() for rid in ids},
        "runner_count_by_race": counts,
        "operator_reviewed_asof_only": True,
        "operator_reviewed_complete_roster": True,
    }
    paths = [tmp_path / n for n in ("history.csv", "entries.csv", "calendar.json")]
    history.to_csv(paths[0], index=False)
    entries.to_csv(paths[1], index=False)
    paths[2].write_text(json.dumps(calendar), encoding="utf-8")
    monkeypatch.setenv("COMPUTERNAME", "DESKTOP-MVV1FD4")
    result = freeze_private_future(
        candidate_dir=candidate, features_csv=paths[1], jra_history_csv=paths[0],
        calendar_json=paths[2], private_output_dir=tmp_path, now_utc=NOW)
    assert result["races"] == 24 and result["runners"] == 144
    assert not result["positive_ev_proven"]
    saved = json.loads((tmp_path/"20261101_JRA_dual_catboost_PRIVATE.json").read_text(encoding="utf-8"))
    assert len(saved["frozen_shadow_PRIVATE"]["races"]) == 24
    assert set(saved["frozen_shadow_PRIVATE"]["races"][0]["roster"]) == set("123456")
    assert saved["hosted_preoff_receipt_verified"] is False
    # Verify explicit adverse source checks with the same native candidate.
    for issue in ("market", "future", "missing", "derived"):
        h, e, _ = _fake_recent_and_entries()
        if issue == "market":
            e["popularity"] = 1
        elif issue == "future":
            h["race_date"] = "2026-11-01"
        elif issue == "missing":
            e = e.iloc[:-1]
        else:
            e["horse_past_starts"] = 999
        with pytest.raises(ValueError):
            prepare_jra_future_shadow_features(
                native, history=h, entries=e, race_day_jst="2026-11-01",
                source_asof=NOW, generated_at=NOW, expected_runner_counts=counts)
