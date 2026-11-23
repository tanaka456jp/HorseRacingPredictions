"""Synthetic-only, offline tests: distinguish empty source CSV from timing failure."""
from __future__ import annotations

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_nar_nonfavorite_private_pair_readiness import audit  # noqa: E402

DAY = "2026-11-10"
RACE = "NAR:20261110:架空競馬場:01"


def _write(tmp_path: Path, *, market=0, win=0, futures=1, closed=0,
           minutes=90, price=None, popularity=None):
    baseline = {
        "schema": "NAR.PC2.OfficialDailyForwardBaseline.v1",
        "day": DAY, "commitment_digest": "fictional-commitment",
        "source_races": 1,
        "complete_private_forecasts": [{
            "race_id": RACE, "race_day": DAY,
            "scheduled_off_utc": "2026-11-10T02:35:00Z",
            "generated_at_utc": "2026-11-10T00:00:00Z",
        }],
    }
    provenance = {
        "schema": "NAR.PC2.OfficialDailyInterimOddsProvenance.v1",
        "frozen_private_forecast_digest": "fictional-commitment",
        "source_generated_utc": "2026-11-10T00:15:00Z",
        "captured_utc": "2026-11-10T00:16:00Z",
        "audit_PRIVATE": {
            "source_day_jst": DAY,
            "market_rows": market, "win_rows": win, "place_rows": 0,
            "registered_flat_races": 1,
            "planned_win_tickets_with_price": int(price is not None),
            "future_preoff_eligible_races": futures,
            "past_or_closed_races": closed,
            "minutes_before_first_scheduled_off": minutes,
        },
        "selected_quotes_PRIVATE": {
            "selected_quotes_PRIVATE": [{
                "race_id": RACE, "win_interim_odds": price,
                "win_popularity": popularity,
            }]
        },
    }
    (tmp_path / "x_baseline_forecast_PRIVATE.json").write_text(
        json.dumps(baseline, ensure_ascii=False), encoding="utf-8"
    )
    (tmp_path / "x_odds_private_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False), encoding="utf-8"
    )
    return provenance


def test_empty_market_during_preoff_window_is_source_coverage_hold(tmp_path):
    _write(tmp_path, futures=1, closed=0, minutes=90)
    result = audit(tmp_path)
    assert result["status"] == "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
    assert result["empty_source_snapshots_with_preoff_eligible_races"] == 1
    assert result["empty_source_snapshots_before_first_off"] == 1
    assert result["empty_source_snapshots_after_first_off"] == 0
    assert result["preoff_eligible_race_observations"] == 1
    assert result["eligible_paired_races"] == 0
    assert result["excluded_missing_preoff_evidence_races"] == 1
    assert result["source_records_exported"] is False
    assert result["after_cost_positive_expected_value_proven"] is False


def test_valid_numeric_string_quote_remains_one_preoff_race(tmp_path):
    _write(tmp_path, market=3, win=2, price="3.20", popularity=2)
    result = audit(tmp_path)
    assert result["eligible_paired_races"] == 1
    assert result["eligible_preoff_quote_rows"] == 1
    assert result["excluded_missing_preoff_evidence_races"] == 0
    assert result["quotes_with_popularity_and_win_odds"] == 1
    assert result["after_cost_positive_expected_value_proven"] is False


def test_invalid_future_closed_count_is_rejected(tmp_path):
    source = _write(tmp_path, futures=1, closed=1, minutes=90)
    result = audit(tmp_path)
    assert result["status"] == "HOLD_PRIVATE_EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID"


def test_after_first_off_can_still_have_later_race_window(tmp_path):
    provenance = _write(tmp_path, futures=1, closed=1, minutes=-6)
    baseline_path = tmp_path / "x_baseline_forecast_PRIVATE.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    # The first race is already closed; the second is still in its
    # ten-minute-plus preoff window. Both remain in the frozen denominator.
    baseline["source_races"] = 2
    baseline["complete_private_forecasts"].append({
        "race_id": "NAR:20261110:架空競馬場:02", "race_day": DAY,
        "scheduled_off_utc": "2026-11-10T00:10:00Z",
        "generated_at_utc": "2026-11-10T00:00:00Z",
    })
    baseline_path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    provenance["audit_PRIVATE"]["registered_flat_races"] = 2
    provenance["selected_quotes_PRIVATE"]["selected_quotes_PRIVATE"].append({
        "race_id": "NAR:20261110:架空競馬場:02",
        "win_interim_odds": None, "win_popularity": None,
    })
    (tmp_path / "x_odds_private_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False), encoding="utf-8"
    )
    result = audit(tmp_path)
    assert result["empty_source_snapshots_after_first_off"] == 1
    assert result["empty_source_snapshots_with_preoff_eligible_races"] == 1
    assert result["preoff_eligible_race_observations"] == 1
    assert result["excluded_missing_preoff_evidence_races"] == 2


def test_immutable_legacy_provenance_without_timing_fields_remains_auditable(tmp_path):
    provenance = _write(tmp_path, futures=1, closed=0, minutes=90)
    for field in ("future_preoff_eligible_races", "past_or_closed_races",
                  "minutes_before_first_scheduled_off"):
        provenance["audit_PRIVATE"].pop(field)
    (tmp_path / "x_odds_private_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False), encoding="utf-8")
    result = audit(tmp_path)
    assert result["status"] == "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
    assert result["timing_derived_from_legacy_provenance_snapshots"] == 1
    assert result["preoff_eligible_race_observations"] == 1
    assert result["empty_source_snapshots_before_first_off"] == 1
    assert result["eligible_preoff_quote_rows"] == 0
    assert result["after_cost_positive_expected_value_proven"] is False


def test_immutable_legacy_zero_default_timing_remains_auditable(tmp_path):
    provenance = _write(tmp_path, futures=0, closed=0, minutes=90)
    (tmp_path / "x_odds_private_provenance.json").write_text(
        json.dumps(provenance, ensure_ascii=False), encoding="utf-8")
    result = audit(tmp_path)
    assert result["status"] == "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
    assert result["timing_derived_from_legacy_provenance_snapshots"] == 1
    assert result["preoff_eligible_race_observations"] == 1
    assert result["snapshots_without_any_win_rows"] == 1
