from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

from .data_sources import load_jra_history_csv
from .ledger import Ledger


@dataclass(frozen=True)
class PaperSettlementSummary:
    unsettled_before: int
    settled_now: int
    wins: int
    losses: int
    pending_missing_race: int
    pending_invalid_race_result: int
    pending_missing_horse: int
    pending_invalid_horse_result: int
    unsettled_after: int
    stake_settled_yen: int
    payout_yen: int
    profit_yen: int


def _post_position_from_horse_id(
    race_id: str,
    horse_id: str,
) -> int | None:
    prefix = f"{race_id}-"
    if not horse_id.startswith(prefix):
        return None
    suffix = horse_id[len(prefix):]
    if not suffix.isdigit():
        return None
    value = int(suffix)
    return value if value > 0 else None


def settle_paper_bets_from_history(
    *,
    ledger: Ledger,
    history: pd.DataFrame,
    source: str,
    source_reference: str = "",
) -> PaperSettlementSummary:
    required = {
        "race_id",
        "post_position",
        "finish_position",
        "win_odds",
    }
    missing = required - set(history.columns)
    if missing:
        raise ValueError(
            f"settlement history missing columns: {sorted(missing)}"
        )
    if not str(source).strip():
        raise ValueError("source must not be empty")

    frame = history.copy()
    frame["race_id"] = frame["race_id"].astype(str)
    for column in (
        "post_position",
        "finish_position",
        "win_odds",
    ):
        frame[column] = pd.to_numeric(
            frame[column],
            errors="coerce",
        )

    bets = ledger.unsettled_paper_bets()
    counters = {
        "settled_now": 0,
        "wins": 0,
        "losses": 0,
        "pending_missing_race": 0,
        "pending_invalid_race_result": 0,
        "pending_missing_horse": 0,
        "pending_invalid_horse_result": 0,
        "stake_settled_yen": 0,
        "payout_yen": 0,
    }

    for bet in bets:
        race_id = str(bet["race_id"])
        horse_id = str(bet["horse_id"])
        race = frame.loc[frame["race_id"] == race_id].copy()
        if race.empty:
            counters["pending_missing_race"] += 1
            continue

        winners = race.loc[race["finish_position"] == 1]
        if len(winners) != 1:
            counters["pending_invalid_race_result"] += 1
            continue

        post_position = _post_position_from_horse_id(
            race_id,
            horse_id,
        )
        if post_position is None:
            counters["pending_missing_horse"] += 1
            continue

        horse_rows = race.loc[
            race["post_position"] == post_position
        ]
        if len(horse_rows) != 1:
            counters["pending_missing_horse"] += 1
            continue

        horse = horse_rows.iloc[0]
        finish = horse["finish_position"]
        if pd.isna(finish) or int(finish) <= 0:
            counters["pending_invalid_horse_result"] += 1
            continue

        won = int(finish) == 1
        final_win_odds = None
        payout = 0
        if won:
            odds = horse["win_odds"]
            if pd.isna(odds) or float(odds) <= 1.0:
                counters["pending_invalid_horse_result"] += 1
                continue
            final_win_odds = float(odds)
            payout = int(
                round(int(bet["stake_yen"]) * final_win_odds)
            )

        created = ledger.record_paper_settlement(
            bet_id=bet["bet_id"],
            race_id=race_id,
            horse_id=horse_id,
            finish_position=int(finish),
            final_win_odds=final_win_odds,
            won=won,
            payout_yen=payout,
            source=source,
            source_reference=source_reference,
        )
        if not created:
            continue

        counters["settled_now"] += 1
        counters["wins" if won else "losses"] += 1
        counters["stake_settled_yen"] += int(bet["stake_yen"])
        counters["payout_yen"] += payout

    unsettled_after = len(ledger.unsettled_paper_bets())
    return PaperSettlementSummary(
        unsettled_before=len(bets),
        unsettled_after=unsettled_after,
        profit_yen=(
            counters["payout_yen"]
            - counters["stake_settled_yen"]
        ),
        **counters,
    )


def settle_paper_bets_from_csv(
    *,
    ledger_path: str | Path,
    history_path: str | Path,
    source: str = "JRA-VAN canonical completed history",
) -> PaperSettlementSummary:
    history = load_jra_history_csv(history_path)
    ledger = Ledger(ledger_path)
    try:
        return settle_paper_bets_from_history(
            ledger=ledger,
            history=history,
            source=source,
            source_reference=str(Path(history_path)),
        )
    finally:
        ledger.close()


def summary_to_dict(
    summary: PaperSettlementSummary,
) -> dict:
    return asdict(summary)
