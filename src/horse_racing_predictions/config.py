from dataclasses import dataclass

@dataclass(frozen=True)
class StrategyConfig:
    min_ev: float = 1.15
    min_probability: float = 0.03
    min_confidence: float = 0.55
    fractional_kelly: float = 0.25
    max_race_fraction: float = 0.02
    max_day_fraction: float = 0.08
    max_bet_yen: int = 10_000
    min_bet_yen: int = 100
    bet_unit_yen: int = 100
    live_execution_enabled: bool = False

DEFAULT_CONFIG = StrategyConfig()
