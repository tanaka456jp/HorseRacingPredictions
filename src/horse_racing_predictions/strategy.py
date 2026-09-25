from .domain import BetDecision
from .ev import is_value_candidate
from .staking import rounded_stake

def decide_win_bet(prediction, bankroll_yen, config):
    eligible, reason = is_value_candidate(
        prediction, config.min_ev, config.min_probability, config.min_confidence
    )
    if not eligible:
        return BetDecision(
            prediction.race_id, prediction.horse_id, prediction.horse_name,
            "WIN", 0, prediction.decimal_odds,
            prediction.expected_return_multiple, prediction.edge,
            reason, prediction.model_version
        )

    stake = rounded_stake(
        bankroll_yen, prediction.predicted_win_probability, prediction.decimal_odds,
        config.fractional_kelly, config.max_race_fraction, config.max_bet_yen,
        config.min_bet_yen, config.bet_unit_yen
    )
    reason = "selected" if stake > 0 else "kelly_non_positive_or_below_unit"
    return BetDecision(
        prediction.race_id, prediction.horse_id, prediction.horse_name,
        "WIN", stake, prediction.decimal_odds,
        prediction.expected_return_multiple, prediction.edge,
        reason, prediction.model_version
    )
