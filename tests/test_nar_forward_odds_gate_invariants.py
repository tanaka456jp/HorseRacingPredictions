"""Fictional-only invariants for the forward odds receipt gate.

No private input, network access, betting, or publication.
This file is deliberately outside the PC2 capture workflow push path filters.
"""
import unittest
from datetime import datetime, timedelta, timezone

from horse_racing_predictions.nar_forward_odds_gate import (
    ForwardOddsGateError,
    validate_forward_receipt,
)


class ForwardOddsGateInvariantTests(unittest.TestCase):
    def fixture(self, n):
        jst = timezone(timedelta(hours=9))
        base = datetime(2026, 11, 13, 9, 0, tzinfo=jst)
        manifest = {
            "race_day_jst": "2026-11-13",
            "frozen_races": n,
            "frozen_horses": n * 7,
            "planned_ticket_count": n * 2,
            "frozen_at_utc": (base - timedelta(hours=3)).isoformat(),
            "first_off_at_utc": (base + timedelta(hours=1)).isoformat(),
        }
        receipt = {
            "source_day_jst": "2026-11-13",
            "observed_at_utc": base.isoformat(),
            "official_source_time_utc": (base - timedelta(minutes=2)).isoformat(),
            "flat_races": n,
            "registered_horses": n * 7,
            "frozen_win_tickets_with_quote": 0,
            "missing_frozen_win_quotes": n,
            "frozen_place_tickets_with_quote": 0,
            "missing_frozen_place_quotes": n,
            "original_forecast_unchanged": True,
            "source_uploaded": False,
            "actual_tickets": 0,
            "after_cost_ev_proven": False,
        }
        return receipt, manifest

    def test_all_quote_coverage_partitions_preserve_denominator(self):
        for n in (1, 3, 12, 59):
            for win in range(n + 1):
                for place in range(n + 1):
                    with self.subTest(n=n, win=win, place=place):
                        receipt, manifest = self.fixture(n)
                        receipt.update(
                            frozen_win_tickets_with_quote=win,
                            missing_frozen_win_quotes=n-win,
                            frozen_place_tickets_with_quote=place,
                            missing_frozen_place_quotes=n-place,
                        )
                        summary = validate_forward_receipt(receipt, manifest)
                        self.assertEqual(summary["winQuoted"] + summary["winMissing"], n)
                        self.assertEqual(summary["placeQuoted"] + summary["placeMissing"], n)
                        self.assertFalse(summary["executablePriceProven"])
                        self.assertFalse(summary["afterCostPositiveEVProven"])

    def test_private_extras_never_echoed(self):
        receipt, manifest = self.fixture(2)
        receipt.update(private_horse_name="DO_NOT_ECHO", private_race_id="SECRET_ID",
                       private_salt="SECRET_SALT", private_zip_bytes="SECRET_ZIP")
        summary = validate_forward_receipt(receipt, manifest)
        output = repr(summary)
        for secret in ("DO_NOT_ECHO", "SECRET_ID", "SECRET_SALT", "SECRET_ZIP"):
            self.assertNotIn(secret, output)

    def test_denominator_and_claim_tampering_rejected(self):
        for field, value in (
            ("missing_frozen_win_quotes", 1),
            ("missing_frozen_place_quotes", 1),
            ("frozen_win_tickets_with_quote", 3),
            ("frozen_place_tickets_with_quote", -1),
            ("actual_tickets", 1),
            ("after_cost_ev_proven", True),
        ):
            with self.subTest(field=field):
                receipt, manifest = self.fixture(2)
                receipt[field] = value
                with self.assertRaises(ForwardOddsGateError):
                    validate_forward_receipt(receipt, manifest)


if __name__ == "__main__":
    unittest.main()
