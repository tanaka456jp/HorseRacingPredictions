import unittest
from horse_racing_predictions.jravan_forward import TrialForwardInputSummary

class TestTrialForwardInputSummary(unittest.TestCase):
    def test_complete_odds_coverage_rate(self):
        # Test when future_entry_races > 0
        summary = TrialForwardInputSummary(
            odds_races=150,
            future_entry_races=50,
            # Other required parameters with default values
        )
        self.assertEqual(summary.complete_odds_coverage_rate, 3.0)

        # Test when future_entry_races = 0
        summary = TrialForwardInputSummary(
            odds_races=100,
            future_entry_races=0,
            # Other required parameters with default values
        )
        self.assertIsNone(summary.complete_odds_coverage_rate)