import math

def kelly_fraction(probability: float, decimal_odds: float) -> float:
    if decimal_odds <= 1.0 or probability <= 0.0:
        return 0.0
    if probability >= 1.0:
        return 1.0
    b = decimal_odds - 1.0
    q = 1.0 - probability
    f = (b * probability - q) / b
    return max(0.0, min(1.0, f))

def rounded_stake(bankroll_yen, probability, decimal_odds, fractional_kelly,
                  max_race_fraction, max_bet_yen, min_bet_yen, bet_unit_yen):
    raw_fraction = kelly_fraction(probability, decimal_odds) * fractional_kelly
    capped_fraction = min(raw_fraction, max_race_fraction)
    raw = min(bankroll_yen * capped_fraction, max_bet_yen)
    stake = math.floor(raw / bet_unit_yen) * bet_unit_yen
    return stake if stake >= min_bet_yen else 0
