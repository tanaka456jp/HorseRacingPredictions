from dataclasses import dataclass
from datetime import datetime
import pandas as pd

from .domain import HorsePrediction
from .strategy import decide_win_bet

@dataclass(frozen=True)
class BacktestSummary:
    bets: int
    stake_yen: int
    payout_yen: int
    profit_yen: int
    roi: float
    ending_bankroll_yen: int
    max_drawdown: float

def _max_drawdown(equity_curve: list[float]) -> float:
    peak = equity_curve[0]
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst

def simulate_win_strategy(
    predictions: pd.DataFrame,
    starting_bankroll_yen: int,
    config,
) -> tuple[pd.DataFrame, BacktestSummary]:
    required = {
        "race_id", "horse_id", "horse_name", "predicted_win_probability",
        "decimal_odds", "confidence", "finish_position", "model_version"
    }
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"missing backtest columns: {sorted(missing)}")

    frame = predictions.copy()
    if "race_date" in frame.columns:
        frame["race_date"] = pd.to_datetime(frame["race_date"], errors="raise")
        frame = frame.sort_values(["race_date", "race_id", "horse_id"])
    else:
        frame = frame.sort_values(["race_id", "horse_id"])

    bankroll = int(starting_bankroll_yen)
    total_stake = 0
    total_payout = 0
    rows = []
    equity = [float(bankroll)]

    for row in frame.itertuples(index=False):
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
        decision = decide_win_bet(p, bankroll, config)
        stake = min(decision.stake_yen, bankroll)
        won = bool(float(row.finish_position) == 1.0)
        payout = int(round(stake * p.decimal_odds)) if stake > 0 and won else 0

        bankroll = bankroll - stake + payout
        total_stake += stake
        total_payout += payout
        equity.append(float(bankroll))

        rows.append({
            "race_id": p.race_id,
            "horse_id": p.horse_id,
            "horse_name": p.horse_name,
            "probability": p.predicted_win_probability,
            "decimal_odds": p.decimal_odds,
            "ev": p.expected_return_multiple,
            "stake_yen": stake,
            "payout_yen": payout,
            "won": won,
            "reason": decision.reason,
            "bankroll_after_yen": bankroll,
        })

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
    )
    return pd.DataFrame(rows), summary
