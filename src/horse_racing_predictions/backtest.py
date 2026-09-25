from dataclasses import dataclass
from datetime import datetime
import math
import pandas as pd

from .domain import HorsePrediction
from .strategy import decide_win_bet
from .validation import FINAL_WIN_ODDS, classify_odds_evidence

@dataclass(frozen=True)
class BacktestSummary:
    bets: int
    stake_yen: int
    payout_yen: int
    profit_yen: int
    roi: float
    ending_bankroll_yen: int
    max_drawdown: float
    odds_evidence: str
    roi_verified: bool
    validation_label: str

def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst

def _round_down(value: float, unit: int) -> int:
    if unit <= 0:
        raise ValueError("bet unit must be positive")
    return int(math.floor(max(0.0, value) / unit) * unit)

def simulate_win_strategy(
    predictions: pd.DataFrame,
    starting_bankroll_yen: int,
    config,
    odds_evidence: str = FINAL_WIN_ODDS,
) -> tuple[pd.DataFrame, BacktestSummary]:
    required = {
        "race_id", "horse_id", "horse_name", "predicted_win_probability",
        "decimal_odds", "confidence", "finish_position", "model_version"
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"missing backtest columns: {sorted(missing)}")
    if starting_bankroll_yen <= 0:
        raise ValueError("starting bankroll must be positive")

    evidence = classify_odds_evidence(odds_evidence)
    frame = predictions.copy()
    if "race_date" in frame.columns:
        frame["race_date"] = pd.to_datetime(frame["race_date"], errors="raise")
        frame["_race_day"] = frame["race_date"].dt.normalize()
        frame = frame.sort_values(["race_date", "race_id", "horse_id"])
    else:
        frame["_race_day"] = pd.NaT
        frame = frame.sort_values(["race_id", "horse_id"])

    bankroll = int(starting_bankroll_yen)
    total_stake = 0
    total_payout = 0
    rows = []
    equity = [float(bankroll)]

    active_day = None
    day_budget_yen = None
    day_stake_yen = 0

    for _, race in frame.groupby("race_id", sort=False):
        race = race.copy()
        race_day = race["_race_day"].iloc[0]

        if pd.notna(race_day):
            if active_day is None or race_day != active_day:
                active_day = race_day
                day_budget_yen = _round_down(
                    bankroll * config.max_day_fraction,
                    config.bet_unit_yen,
                )
                day_stake_yen = 0
            remaining_day_budget = max(
                0,
                int(day_budget_yen) - day_stake_yen,
            )
        else:
            remaining_day_budget = bankroll

        race_start_bankroll = bankroll
        race_budget = _round_down(
            race_start_bankroll * config.max_race_fraction,
            config.bet_unit_yen,
        )
        available_budget = min(
            race_start_bankroll,
            race_budget,
            remaining_day_budget,
        )

        candidates = []
        for row in race.itertuples(index=False):
            p = HorsePrediction(
                race_id=str(row.race_id),
                horse_id=str(row.horse_id),
                horse_name=str(row.horse_name),
                predicted_win_probability=float(row.predicted_win_probability),
                decimal_odds=float(row.decimal_odds),
                confidence=float(row.confidence),
                model_version=str(row.model_version),
                predicted_at=datetime.now(),
            )
            decision = decide_win_bet(
                p,
                race_start_bankroll,
                config,
            )
            candidates.append((row, p, decision))

        candidates.sort(
            key=lambda item: (
                item[2].edge,
                item[1].predicted_win_probability,
            ),
            reverse=True,
        )

        race_stake = 0
        race_payout = 0
        race_rows = []

        for row, p, decision in candidates:
            desired = int(decision.stake_yen)
            remaining = max(0, available_budget - race_stake)
            stake = min(desired, remaining)
            stake = _round_down(stake, config.bet_unit_yen)

            reason = decision.reason
            if desired > 0 and stake == 0:
                reason = "race_or_day_budget_exhausted"
            elif 0 < stake < desired:
                reason = "selected_budget_capped"

            won = bool(float(row.finish_position) == 1.0)
            payout = (
                int(round(stake * p.decimal_odds))
                if stake > 0 and won
                else 0
            )

            race_stake += stake
            race_payout += payout
            race_rows.append({
                "race_id": p.race_id,
                "horse_id": p.horse_id,
                "horse_name": p.horse_name,
                "probability": p.predicted_win_probability,
                "decimal_odds": p.decimal_odds,
                "ev": p.expected_return_multiple,
                "stake_yen": stake,
                "payout_yen": payout,
                "won": won,
                "reason": reason,
            })

        bankroll = bankroll - race_stake + race_payout
        total_stake += race_stake
        total_payout += race_payout
        day_stake_yen += race_stake
        equity.append(float(bankroll))

        for detail in race_rows:
            detail["bankroll_after_yen"] = bankroll
            rows.append(detail)

    profit = total_payout - total_stake
    roi = (total_payout / total_stake - 1.0) if total_stake else 0.0
    summary = BacktestSummary(
        bets=sum(1 for r in rows if r["stake_yen"] > 0),
        stake_yen=total_stake,
        payout_yen=total_payout,
        profit_yen=profit,
        roi=roi,
        ending_bankroll_yen=bankroll,
        max_drawdown=_max_drawdown(equity),
        odds_evidence=evidence.odds_evidence,
        roi_verified=evidence.roi_verified,
        validation_label=evidence.label,
    )
    return pd.DataFrame(rows), summary
