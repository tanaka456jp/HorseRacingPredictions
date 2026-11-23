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
    assert result["empty_source_lead_30_to_119min"] == 1
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
    assert result["empty_source_lead_120_to_239min"] == 1
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


def test_early_empty_source_is_not_mistaken_for_near_off(tmp_path):
    _write(tmp_path, futures=1, closed=0, minutes=360)
    result = audit(tmp_path)
    assert result["status"] == "HOLD_OFFICIAL_ODDS_CSV_NO_MARKET_ROWS"
    assert result["empty_source_lead_ge_240min"] == 1
    assert result["empty_source_lead_0_to_29min"] == 0


def _write_offline_manual_sidecar(tmp_path, *, odds="3.2", popularity=2,
                                  bad_digest=False):
    provenance = {
        "schema": "NAR.PC2.ManuallyDownloadedDailyOddsAuditPrivate.v1",
        "download_mode": "USER_SUPPLIED_OFFLINE_NO_PROVIDER_REQUEST",
        "individual_authorized_automated_polling": False,
        "source_hostname_independently_attested": False,
        "independent_hosted_receipt_verified": False,
        "actual_order_execution_verified": False,
        "positive_ev_proven": False,
        "source_uploaded": False,
        "source_zip_filename_PRIVATE": "20261110_1794269700_odds.zip",
        "frozen_forecast_commitment_PRIVATE": (
            "wrong-digest" if bad_digest else "fictional-commitment"),
        "local_receipt_utc": "2026-11-10T00:16:00Z",
        "audit_PRIVATE": {
            "source_day_jst": DAY,
            "registered_flat_races": 1, "market_rows": 5,
            "win_rows": 3, "place_rows": 2,
            "planned_win_tickets_with_price": int(odds is not None),
            "source_generated_at_utc": "2026-11-10T00:15:00Z",
            "observed_at_utc": "2026-11-10T00:16:00Z",
        },
        "quotes_PRIVATE": {"selected_quotes_PRIVATE": [{
            "race_id": RACE, "win_interim_odds": odds,
            "win_popularity": popularity,
        }]},
    }
    path = tmp_path / "a_manually_downloaded_odds_PRIVATE.json"
    path.write_text(json.dumps(provenance, ensure_ascii=False), encoding="utf-8")
    return path


def test_manual_offline_quote_is_reported_separately_without_ev_proof(tmp_path):
    _write(tmp_path)
    (tmp_path / "x_odds_private_provenance.json").unlink()
    _write_offline_manual_sidecar(tmp_path)
    result = audit(tmp_path)
    assert result["status"] == "HOLD_MANUAL_OFFLINE_SOURCE_NOT_INDEPENDENTLY_ATTESTED"
    assert result["manual_offline_odds_provenance_files"] == 1
    assert result["manual_offline_market_rows"] == 5
    assert result["manual_offline_win_rows"] == 3
    assert result["manual_offline_matched_quote_rows"] == 1
    assert result["manual_offline_verified_chronology_quote_rows"] == 1
    assert result["manual_offline_distinct_races_with_quote"] == 1
    assert result["eligible_paired_races"] == 0
    assert result["official_csv_market_rows"] == 0
    assert result["after_cost_positive_expected_value_proven"] is False
    assert result["source_records_exported"] is False


def test_manual_missing_price_is_hold_without_mislabeling_complete(tmp_path):
    _write(tmp_path)
    (tmp_path / "x_odds_private_provenance.json").unlink()
    _write_offline_manual_sidecar(tmp_path, odds=None, popularity=None)
    result = audit(tmp_path)
    assert result["status"] == "HOLD_MANUAL_OFFLINE_NO_VERIFIED_PREOFF_WIN_QUOTES"
    assert result["manual_offline_missing_win_quote_rows"] == 1
    assert result["manual_offline_distinct_races_with_quote"] == 0


def test_manual_invalid_digest_is_not_accepted(tmp_path):
    _write(tmp_path)
    (tmp_path / "x_odds_private_provenance.json").unlink()
    _write_offline_manual_sidecar(tmp_path, bad_digest=True)
    assert audit(tmp_path)["status"] == "HOLD_PRIVATE_EVIDENCE_SCHEMA_OR_PROVENANCE_INVALID"
