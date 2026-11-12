"""Fictional-only regression for the forward NAR receipt gate."""
from datetime import datetime, timedelta, timezone
import unittest

from horse_racing_predictions.nar_forward_odds_gate import (
    ForwardOddsGateError, validate_forward_receipt,
)


class ForwardOddsGateTests(unittest.TestCase):
    def fixture(self, races):
        jst = timezone(timedelta(hours=9))
        day = "2026-11-12"
        base = datetime(2026, 11, 12, 11, 0, tzinfo=jst)
        iso = lambda dt: dt.isoformat()
        manifest = dict(race_day_jst=day, frozen_races=races,
                        frozen_horses=races * 8, planned_ticket_count=2*races,
                        frozen_at_utc=iso(base - timedelta(hours=2)),
                        first_off_at_utc=iso(base + timedelta(hours=1)))
        receipt = dict(source_day_jst=day, observed_at_utc=iso(base),
                       official_source_time_utc=iso(base - timedelta(minutes=1)),
                       flat_races=races, registered_horses=races*8,
                       frozen_win_tickets_with_quote=0,
                       frozen_place_tickets_with_quote=0,
                       missing_frozen_win_quotes=races,
                       missing_frozen_place_quotes=races,
                       original_forecast_unchanged=True, source_uploaded=False,
                       actual_tickets=0, after_cost_ev_proven=False)
        return receipt, manifest

    def test_fictional_variable_days_and_missing_quotes(self):
        for races in (1, 2, 59):
            with self.subTest(races=races):
                receipt, manifest = self.fixture(races)
                result = validate_forward_receipt(receipt, manifest)
                self.assertEqual(result["frozenRaces"], races)
                self.assertFalse(result["executablePriceProven"])
                self.assertNotIn("official_source_time_utc", result)

    def test_fail_closed_mutations(self):
        cases = [
            ("source_day_jst", "2026-11-10", "receipt"),
            ("flat_races", 59, "receipt"),
            ("registered_horses", 999, "receipt"),
            ("missing_frozen_win_quotes", 0, "receipt"),
            ("missing_frozen_place_quotes", 0, "receipt"),
            ("observed_at_utc", "2026-11-12T12:00:00+09:00", "receipt"),
            ("official_source_time_utc", "2026-11-12T12:00:00+09:00", "receipt"),
            ("observed_at_utc", "invalid", "receipt"),
            ("source_uploaded", True, "receipt"),
            ("after_cost_ev_proven", True, "receipt"),
            ("planned_ticket_count", 1, "manifest"),
            ("race_day_jst", "2026-11-10", "manifest"),
        ]
        for key, value, where in cases:
            with self.subTest(key=key, value=value):
                receipt, manifest = self.fixture(2)
                (receipt if where == "receipt" else manifest)[key] = value
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(receipt, manifest)


    def test_fictional_source_and_freeze_chronology_fail_closed(self):
        # All examples are synthetic; no private NAR records are used.
        receipt, manifest = self.fixture(2)
        cases = [
            ("official_source_time_utc", "2026-11-11T23:59:59+09:00", "receipt"),
            ("official_source_time_utc", "2026-11-12T11:00:01+09:00", "receipt"),
            ("official_source_time_utc", "2026-11-12T09:00:00+09:00", "receipt"),
            ("frozen_at_utc", "2026-11-12T10:59:00+09:00", "manifest"),
            ("first_off_at_utc", "2026-11-13T12:00:00+09:00", "manifest"),
            ("observed_at_utc", "2026-11-12T11:00:00", "receipt"),
        ]
        for key, value, target in cases:
            with self.subTest(key=key, value=value):
                r, m = self.fixture(2)
                (r if target == "receipt" else m)[key] = value
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(r, m)

    def test_fictional_partial_quote_coverage_does_not_prove_execution(self):
        receipt, manifest = self.fixture(3)
        receipt.update(frozen_win_tickets_with_quote=2,
                       missing_frozen_win_quotes=1,
                       frozen_place_tickets_with_quote=1,
                       missing_frozen_place_quotes=2)
        summary = validate_forward_receipt(receipt, manifest)
        self.assertEqual((summary["winQuoted"], summary["winMissing"]), (2, 1))
        self.assertEqual((summary["placeQuoted"], summary["placeMissing"]), (1, 2))
        self.assertFalse(summary["executablePriceProven"])
        self.assertFalse(summary["afterCostPositiveEVProven"])

    def test_fictional_time_and_denominator_boundaries(self):
        receipt, manifest = self.fixture(2)
        receipt["observed_at_utc"] = "2026-11-12T11:50:00+09:00"
        receipt["official_source_time_utc"] = "2026-11-12T11:49:00+09:00"
        self.assertEqual(validate_forward_receipt(receipt, manifest)["frozenRaces"], 2)
        receipt["observed_at_utc"] = "2026-11-12T11:50:01+09:00"
        with self.assertRaises(ForwardOddsGateError):
            validate_forward_receipt(receipt, manifest)
        receipt, manifest = self.fixture(2)
        receipt["frozen_win_tickets_with_quote"] = True
        with self.assertRaises(ForwardOddsGateError):
            validate_forward_receipt(receipt, manifest)
        receipt, manifest = self.fixture(2)
        manifest["frozen_horses"] = 1
        with self.assertRaises(ForwardOddsGateError):
            validate_forward_receipt(receipt, manifest)


if __name__ == "__main__":
    unittest.main()
