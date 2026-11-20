"""Fictional-only chronology and manifest integrity regression tests.

No provider calls, private files, publication, or betting.
"""
import unittest
from datetime import datetime, timedelta, timezone

from horse_racing_predictions.nar_forward_odds_gate import (
    ForwardOddsGateError,
    validate_forward_receipt,
)


class ForwardReceiptChronologyTests(unittest.TestCase):
    def fixture(self):
        jst = timezone(timedelta(hours=9))
        day = datetime(2026, 11, 14, 9, tzinfo=jst)
        manifest = {
            "race_day_jst": "2026-11-14",
            "frozen_races": 2,
            "frozen_horses": 14,
            "planned_ticket_count": 4,
            "frozen_at_utc": (day - timedelta(hours=3)).isoformat(),
            "first_off_at_utc": (day + timedelta(hours=1)).isoformat(),
        }
        receipt = {
            "source_day_jst": "2026-11-14",
            "observed_at_utc": day.isoformat(),
            "official_source_time_utc": (day - timedelta(minutes=2)).isoformat(),
            "flat_races": 2,
            "registered_horses": 14,
            "frozen_win_tickets_with_quote": 0,
            "missing_frozen_win_quotes": 2,
            "frozen_place_tickets_with_quote": 0,
            "missing_frozen_place_quotes": 2,
            "original_forecast_unchanged": True,
            "source_uploaded": False,
            "actual_tickets": 0,
            "after_cost_ev_proven": False,
        }
        return receipt, manifest

    def test_chronological_boundaries_fail_closed(self):
        for mutation in ("source_after_observation", "freeze_after_source",
                         "observation_at_first_off", "nine_minutes_before_off",
                         "missing_timezone"):
            with self.subTest(mutation=mutation):
                receipt, manifest = self.fixture()
                if mutation == "source_after_observation":
                    receipt["official_source_time_utc"] = (
                        datetime.fromisoformat(receipt["observed_at_utc"])
                        + timedelta(seconds=1)).isoformat()
                elif mutation == "freeze_after_source":
                    manifest["frozen_at_utc"] = receipt["official_source_time_utc"]
                elif mutation == "observation_at_first_off":
                    receipt["observed_at_utc"] = manifest["first_off_at_utc"]
                elif mutation == "nine_minutes_before_off":
                    receipt["observed_at_utc"] = (
                        datetime.fromisoformat(manifest["first_off_at_utc"])
                        - timedelta(minutes=9)).isoformat()
                else:
                    receipt["official_source_time_utc"] = "2026-11-14T08:58:00"
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(receipt, manifest)

    def test_exact_ten_minute_boundary_is_allowed_but_not_executable(self):
        receipt, manifest = self.fixture()
        receipt["observed_at_utc"] = (
            datetime.fromisoformat(manifest["first_off_at_utc"])
            - timedelta(minutes=10)).isoformat()
        summary = validate_forward_receipt(receipt, manifest)
        self.assertFalse(summary["executablePriceProven"])
        self.assertFalse(summary["afterCostPositiveEVProven"])

    def test_aggregate_counts_are_not_proof_of_execution(self):
        receipt, manifest = self.fixture()
        receipt.update(frozen_win_tickets_with_quote=2,
                       missing_frozen_win_quotes=0,
                       frozen_place_tickets_with_quote=2,
                       missing_frozen_place_quotes=0)
        summary = validate_forward_receipt(receipt, manifest)
        self.assertEqual(summary["winQuoted"], 2)
        self.assertEqual(summary["placeQuoted"], 2)
        self.assertFalse(summary["executablePriceProven"])
        self.assertFalse(summary["afterCostPositiveEVProven"])


if __name__ == "__main__":
    unittest.main()
