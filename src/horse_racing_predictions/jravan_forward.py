class TrialForwardInputSummary:
    def __init__(
        self,
        odds_races: int,
        future_entry_races: int,
        # Other required parameters with default values
    ):
        self.odds_races = odds_races
        self.future_entry_races = future_entry_races
        # Initialize other parameters

    @property
    def complete_odds_coverage_rate(self):
        if self.future_entry_races > 0:
            return self.odds_races / self.future_entry_races
        return None