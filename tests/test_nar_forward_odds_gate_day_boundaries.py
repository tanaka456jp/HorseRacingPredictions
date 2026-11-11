"""Fictional-only forward audit: reject cross-day and untrusted economic claims.

No provider access, PC2 files, race identities, odds or real tickets.
"""
import unittest
from datetime import datetime, timedelta, timezone

from horse_racing_predictions.nar_forward_odds_gate import (
    ForwardOddsGateError, validate_forward_receipt,
)


class ForwardDayBoundaryTests(unittest.TestCase):
    def setUp(self):
        jst = timezone(timedelta(hours=9))
        t = datetime(2026, 11, 15, 8, 0, tzinfo=jst)
        self.manifest = dict(
            race_day_jst="2026-11-15", frozen_races=3, frozen_horses=21,
            planned_ticket_count=6,
            frozen_at_utc=(t - timedelta(hours=2)).isoformat(),
            first_off_at_utc=(t + timedelta(hours=2)).isoformat(),
        )
        self.receipt = dict(
            source_day_jst="2026-11-15",
            observed_at_utc=t.isoformat(),
            official_source_time_utc=(t - timedelta(minutes=5)).isoformat(),
            flat_races=3, registered_horses=21,
            frozen_win_tickets_with_quote=1, missing_frozen_win_quotes=2,
            frozen_place_tickets_with_quote=0, missing_frozen_place_quotes=3,
            original_forecast_unchanged=True, source_uploaded=False,
            actual_tickets=0, after_cost_ev_proven=False,
        )

    def test_missing_prices_remain_in_full_frozen_denominator(self):
        summary = validate_forward_receipt(self.receipt, self.manifest)
        self.assertEqual(summary["winQuoted"] + summary["winMissing"], 3)
        self.assertEqual(summary["placeQuoted"] + summary["placeMissing"], 3)
        self.assertFalse(summary["executablePriceProven"])
        self.assertFalse(summary["afterCostPositiveEVProven"])

    def test_observed_jst_day_mismatch_even_if_source_day_claims_match(self):
        self.receipt["observed_at_utc"] = "2026-11-14T14:59:59Z"
        with self.assertRaises(ForwardOddsGateError) as cm:
            validate_forward_receipt(self.receipt, self.manifest)
        self.assertEqual(str(cm.exception), "OBSERVED_DAY_MISMATCH")

    def test_no_inferred_denominator_from_download(self):
        for field, value in (("flat_races", 2), ("registered_horses", 20),
                             ("missing_frozen_win_quotes", 1),
                             ("missing_frozen_place_quotes", 2)):
            with self.subTest(field=field):
                receipt = dict(self.receipt, **{field: value})
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(receipt, self.manifest)

    def test_boolean_and_fake_economic_claims_fail_closed(self):
        for field, value in (("actual_tickets", True),
                             ("after_cost_ev_proven", True),
                             ("source_uploaded", True),
                             ("original_forecast_unchanged", 1)):
            with self.subTest(field=field):
                receipt = dict(self.receipt, **{field: value})
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(receipt, self.manifest)


if __name__ == "__main__":
    unittest.main()
