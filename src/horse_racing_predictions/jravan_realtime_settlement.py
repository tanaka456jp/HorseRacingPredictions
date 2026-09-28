from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import tempfile
from typing import Callable

import pandas as pd

from .jravan import JraVanApiError, JvLinkClient
from .jravan_parser import parse_raw_jsonl
from .jravan_trial import filter_single_winner_races
from .ledger import Ledger
from .paper_settlement import settle_paper_bets_from_history


@dataclass(frozen=True)
class RealtimeSettlementSummary:
    status: str
    unsettled_before: int
    races_requested: int
    races_completed: int
    realtime_errors: int
    settled_now: int
    wins: int
    losses: int
    unsettled_after: int
    stake_settled_yen: int
    payout_yen: int
    profit_yen: int


def realtime_result_key_from_race_id(race_id: str) -> str:
    parts = str(race_id).split("-")
    if len(parts) != 5:
        raise ValueError(
            "race_id must be YYYYMMDD-CC-MM-DD-RR"
        )
    race_date, course, meet, day, race = parts
    if (
        len(race_date) != 8
        or len(course) != 2
        or len(meet) != 2
        or len(day) != 2
        or len(race) != 2
        or not all(
            value.isdigit()
            for value in (race_date, course, meet, day, race)
        )
    ):
        raise ValueError(
            "race_id must be numeric YYYYMMDD-CC-MM-DD-RR"
        )
    return f"{race_date}{course}{race}"


def capture_completed_race_0b12(
    race_id: str,
    *,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
    wait_retries: int | None = None,
    wait_seconds: float | None = None,
) -> pd.DataFrame:
    key = realtime_result_key_from_race_id(race_id)
    client = client_factory()
    records = []

    try:
        if not client.initialized:
            client.initialize()
        client.open_realtime(
            dataspec="0B12",
            key=key,
        )
        read_kwargs = {}
        if wait_retries is not None:
            if wait_retries < 0:
                raise ValueError("wait_retries must be non-negative")
            read_kwargs["wait_retries"] = int(wait_retries)
        if wait_seconds is not None:
            if wait_seconds < 0:
                raise ValueError("wait_seconds must be non-negative")
            read_kwargs["wait_seconds"] = float(wait_seconds)

        for record in client.iter_records(**read_kwargs):
            if record.record_type in {"RA", "SE"}:
                records.append({
                    "record_type": record.record_type,
                    "text": record.text,
                    "file_name": record.file_name,
                })
    finally:
        if client.opened:
            client.close()
        else:
            client.close()

    if not records:
        return pd.DataFrame()

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            suffix=".jsonl",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            for row in records:
                handle.write(
                    json.dumps(row, ensure_ascii=False) + "\n"
                )

        frame, _report = parse_raw_jsonl(
            temp_path,
            completed_only=True,
        )
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)

    if frame.empty:
        return frame

    frame = frame.loc[
        frame["race_id"].astype(str) == str(race_id)
    ].copy()
    if frame.empty:
        return frame

    completed, _winner_report = filter_single_winner_races(
        frame
    )
    return completed


def run_realtime_paper_settlement(
    *,
    ledger_path: str | Path,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
) -> RealtimeSettlementSummary:
    ledger = Ledger(ledger_path)
    try:
        unsettled = ledger.unsettled_paper_bets()
        if not unsettled:
            return RealtimeSettlementSummary(
                status="no_unsettled_bets",
                unsettled_before=0,
                races_requested=0,
                races_completed=0,
                realtime_errors=0,
                settled_now=0,
                wins=0,
                losses=0,
                unsettled_after=0,
                stake_settled_yen=0,
                payout_yen=0,
                profit_yen=0,
            )

        race_ids = sorted({
            str(row["race_id"])
            for row in unsettled
        })
        frames = []
        realtime_errors = 0
        completed_races = 0

        for race_id in race_ids:
            try:
                frame = capture_completed_race_0b12(
                    race_id,
                    client_factory=client_factory,
                )
            except (JraVanApiError, ValueError):
                realtime_errors += 1
                continue

            if frame.empty:
                continue
            frames.append(frame)
            completed_races += 1

        if frames:
            history = pd.concat(
                frames,
                ignore_index=True,
                sort=False,
            )
            settlement = settle_paper_bets_from_history(
                ledger=ledger,
                history=history,
                source="JRA-VAN 0B12 completed-race realtime",
                source_reference="JVRTOpen:0B12",
            )
            unsettled_after = settlement.unsettled_after
            settled_now = settlement.settled_now
            wins = settlement.wins
            losses = settlement.losses
            stake_settled_yen = settlement.stake_settled_yen
            payout_yen = settlement.payout_yen
            profit_yen = settlement.profit_yen
        else:
            unsettled_after = len(
                ledger.unsettled_paper_bets()
            )
            settled_now = 0
            wins = 0
            losses = 0
            stake_settled_yen = 0
            payout_yen = 0
            profit_yen = 0

        status = (
            "settled"
            if settled_now > 0
            else "pending_results"
        )
        return RealtimeSettlementSummary(
            status=status,
            unsettled_before=len(unsettled),
            races_requested=len(race_ids),
            races_completed=completed_races,
            realtime_errors=realtime_errors,
            settled_now=settled_now,
            wins=wins,
            losses=losses,
            unsettled_after=unsettled_after,
            stake_settled_yen=stake_settled_yen,
            payout_yen=payout_yen,
            profit_yen=profit_yen,
        )
    finally:
        ledger.close()


def summary_to_dict(
    summary: RealtimeSettlementSummary,
) -> dict:
    return asdict(summary)
