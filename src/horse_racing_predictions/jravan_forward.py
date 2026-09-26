from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from .jravan import JraVanApiError, JvLinkClient
from .jravan_parser import (
    CENTRAL_RACECOURSES,
    DATA_PRIORITY,
    parse_ra,
    parse_raw_jsonl,
)


JST = timezone(timedelta(hours=9), name="JST")
REALTIME_WIN_ODDS_DATASPEC = "0B31"


@dataclass(frozen=True)
class RaceSchedule:
    race_id: str
    data_division: str
    scheduled_post_time: datetime


@dataclass(frozen=True)
class WinOddsItem:
    post_position: int
    decimal_odds: float
    popularity: int | None


@dataclass(frozen=True)
class WinOddsRecord:
    race_id: str
    data_division: str
    published_mmddhhmm: str
    registered_count: int | None
    runner_count: int | None
    items: tuple[WinOddsItem, ...]


@dataclass(frozen=True)
class TrialForwardInputSummary:
    status: str
    history_cutoff: str
    captured_at: str
    decision_time: str | None
    current_week_rows: int
    current_week_races: int
    future_entry_rows: int
    future_entry_races: int
    odds_rows: int
    odds_races: int
    skipped_races_no_complete_odds: int
    earliest_post_time: str | None
    latest_post_time: str | None
    entries_path: str | None
    odds_path: str | None


def _raw_bytes(text: str) -> bytes:
    try:
        return text.encode("cp932")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "JV-Data record could not be round-tripped to CP932"
        ) from exc


def _slice_ascii(raw: bytes, position: int, length: int) -> str:
    start = position - 1
    end = start + length
    if len(raw) < end:
        raise ValueError(
            f"record is too short for position={position}, length={length}: "
            f"{len(raw)} bytes"
        )
    return raw[start:end].decode("ascii", errors="replace").strip()


def _int_ascii(
    raw: bytes,
    position: int,
    length: int,
    *,
    zero_is_none: bool = False,
) -> int | None:
    value = _slice_ascii(raw, position, length)
    if not value or not value.isdigit():
        return None
    number = int(value)
    if zero_is_none and number == 0:
        return None
    return number


def _race_id_from_raw(raw: bytes) -> str:
    year = _slice_ascii(raw, 12, 4)
    mmdd = _slice_ascii(raw, 16, 4)
    course = _slice_ascii(raw, 20, 2)
    meet = _slice_ascii(raw, 22, 2)
    day = _slice_ascii(raw, 24, 2)
    race = _slice_ascii(raw, 26, 2)
    if not (
        len(year) == 4
        and len(mmdd) == 4
        and course
        and meet
        and day
        and race
    ):
        raise ValueError("invalid JV-Data race key")
    return f"{year}{mmdd}-{course}-{meet}-{day}-{race}"


def _data_priority(value: str) -> int:
    return DATA_PRIORITY.get(value, -1)


def _scheduled_post_time_from_ra(text: str) -> RaceSchedule:
    record = parse_ra(text)
    raw = _raw_bytes(text)
    hhmm = _slice_ascii(raw, 874, 4)
    if len(hhmm) != 4 or not hhmm.isdigit():
        raise ValueError(
            f"RA scheduled post time is invalid for {record.race_id}: {hhmm!r}"
        )
    hour = int(hhmm[:2])
    minute = int(hhmm[2:])
    if hour > 23 or minute > 59:
        raise ValueError(
            f"RA scheduled post time is invalid for {record.race_id}: {hhmm}"
        )
    race_date = datetime.strptime(
        record.race_date,
        "%Y-%m-%d",
    ).date()
    scheduled = datetime(
        race_date.year,
        race_date.month,
        race_date.day,
        hour,
        minute,
        tzinfo=JST,
    )
    return RaceSchedule(
        race_id=record.race_id,
        data_division=record.data_division,
        scheduled_post_time=scheduled,
    )


def _selected_race_schedules(
    raw_path: str | Path,
) -> dict[str, RaceSchedule]:
    selected: dict[str, RaceSchedule] = {}
    with Path(raw_path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if str(payload.get("record_type", "")) != "RA":
                continue
            text = str(payload["text"])
            try:
                schedule = _scheduled_post_time_from_ra(text)
            except Exception as exc:
                raise ValueError(
                    f"invalid RA schedule on JSONL line {line_number}: {exc}"
                ) from exc
            course = schedule.race_id.split("-")[1]
            if course not in CENTRAL_RACECOURSES:
                continue
            current = selected.get(schedule.race_id)
            if (
                current is None
                or _data_priority(schedule.data_division)
                >= _data_priority(current.data_division)
            ):
                selected[schedule.race_id] = schedule
    return selected


def build_future_entries_from_current_week(
    raw_path: str | Path,
    *,
    history_cutoff: str | pd.Timestamp,
    now: datetime | None = None,
    min_lead_minutes: int = 10,
) -> tuple[pd.DataFrame, dict[str, RaceSchedule], dict]:
    if min_lead_minutes < 0:
        raise ValueError("min_lead_minutes must be non-negative")
    now = now or datetime.now(JST)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    now = now.astimezone(JST)

    frame, report = parse_raw_jsonl(
        raw_path,
        completed_only=False,
    )
    schedules = _selected_race_schedules(raw_path)

    if frame.empty:
        return frame, {}, {
            "current_week_rows": 0,
            "current_week_races": 0,
        }

    cutoff = pd.Timestamp(history_cutoff).normalize()
    threshold = now + timedelta(minutes=min_lead_minutes)

    frame = frame.copy()
    frame["race_date"] = pd.to_datetime(
        frame["race_date"],
        errors="raise",
    )

    valid_races = {
        race_id: schedule
        for race_id, schedule in schedules.items()
        if pd.Timestamp(schedule.scheduled_post_time.date()) > cutoff
        and schedule.scheduled_post_time > threshold
    }

    entries = frame.loc[
        frame["race_id"].astype(str).isin(valid_races)
    ].copy()

    if "_jv_abnormal_code" in entries.columns:
        abnormal = entries["_jv_abnormal_code"].fillna("").astype(str)
        entries = entries.loc[abnormal.isin({"", "0"})].copy()

    entries = entries.loc[
        entries["post_position"].notna()
        & entries["horse_name"].fillna("").astype(str).str.strip().ne("")
    ].copy()

    safe_races: list[str] = []
    for race_id, group in entries.groupby("race_id", sort=False):
        positions = pd.to_numeric(
            group["post_position"],
            errors="coerce",
        )
        if positions.isna().any():
            continue
        if positions.duplicated().any():
            continue
        if len(group) < 2:
            continue
        safe_races.append(str(race_id))

    entries = entries.loc[
        entries["race_id"].astype(str).isin(safe_races)
    ].copy()
    entries = entries.sort_values(
        ["race_date", "race_id", "post_position"],
        kind="stable",
    ).reset_index(drop=True)

    safe_schedules = {
        race_id: valid_races[race_id]
        for race_id in safe_races
        if race_id in valid_races
    }

    return entries, safe_schedules, {
        "current_week_rows": int(report.output_rows),
        "current_week_races": int(report.output_races),
    }


def parse_o1_win_odds(text: str) -> WinOddsRecord:
    raw = _raw_bytes(text)
    if _slice_ascii(raw, 1, 2) != "O1":
        raise ValueError("not an O1 record")
    if len(raw) < 267:
        raise ValueError(
            f"O1 record must contain at least 267 data bytes, got {len(raw)}"
        )

    race_id = _race_id_from_raw(raw)
    data_division = _slice_ascii(raw, 3, 1)
    published = _slice_ascii(raw, 28, 8)
    registered_count = _int_ascii(raw, 36, 2)
    runner_count = _int_ascii(raw, 38, 2)

    items: list[WinOddsItem] = []
    for index in range(28):
        start = 44 + index * 8
        post_position = _int_ascii(
            raw,
            start,
            2,
            zero_is_none=True,
        )
        odds_text = _slice_ascii(raw, start + 2, 4)
        popularity = _int_ascii(
            raw,
            start + 6,
            2,
            zero_is_none=True,
        )
        if post_position is None:
            continue
        if not odds_text.isdigit():
            continue
        odds_value = int(odds_text)
        if odds_value <= 0:
            continue
        decimal_odds = odds_value / 10.0
        if decimal_odds <= 1.0:
            continue
        items.append(
            WinOddsItem(
                post_position=post_position,
                decimal_odds=decimal_odds,
                popularity=popularity,
            )
        )

    return WinOddsRecord(
        race_id=race_id,
        data_division=data_division,
        published_mmddhhmm=published,
        registered_count=registered_count,
        runner_count=runner_count,
        items=tuple(items),
    )


def _race_id_to_realtime_key(race_id: str) -> str:
    parts = race_id.split("-")
    if len(parts) != 5:
        raise ValueError(f"invalid canonical race_id: {race_id}")
    key = "".join(parts)
    if len(key) != 16 or not key.isdigit():
        raise ValueError(f"invalid realtime race key: {race_id}")
    return key


def _select_latest_o1(
    records: list[WinOddsRecord],
) -> WinOddsRecord | None:
    selected = None
    for record in records:
        if (
            selected is None
            or _data_priority(record.data_division)
            >= _data_priority(selected.data_division)
        ):
            selected = record
    return selected


def capture_complete_win_odds(
    entries: pd.DataFrame,
    schedules: dict[str, RaceSchedule],
    *,
    min_lead_minutes: int = 10,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
    now_fn: Callable[[], datetime] | None = None,
) -> tuple[pd.DataFrame, int]:
    if min_lead_minutes < 0:
        raise ValueError("min_lead_minutes must be non-negative")
    now_fn = now_fn or (lambda: datetime.now(JST))

    rows: list[dict] = []
    skipped = 0

    for race_id, race_entries in entries.groupby(
        "race_id",
        sort=False,
    ):
        race_id = str(race_id)
        schedule = schedules.get(race_id)
        if schedule is None:
            skipped += 1
            continue

        observed_at = now_fn().astimezone(JST)
        if (
            schedule.scheduled_post_time
            <= observed_at + timedelta(minutes=min_lead_minutes)
        ):
            skipped += 1
            continue

        client = client_factory()
        parsed_records: list[WinOddsRecord] = []
        try:
            client.initialize()
            client.open_realtime(
                dataspec=REALTIME_WIN_ODDS_DATASPEC,
                key=_race_id_to_realtime_key(race_id),
            )
            for raw_record in client.iter_records():
                if raw_record.record_type != "O1":
                    continue
                parsed = parse_o1_win_odds(raw_record.text)
                if parsed.race_id == race_id:
                    parsed_records.append(parsed)
        except JraVanApiError:
            skipped += 1
            continue
        finally:
            client.close()

        selected = _select_latest_o1(parsed_records)
        if selected is None:
            skipped += 1
            continue

        odds_by_position = {
            item.post_position: item
            for item in selected.items
        }
        expected_positions = {
            int(value)
            for value in pd.to_numeric(
                race_entries["post_position"],
                errors="raise",
            ).tolist()
        }
        if not expected_positions:
            skipped += 1
            continue
        if not expected_positions.issubset(odds_by_position):
            skipped += 1
            continue

        observed_at = now_fn().astimezone(JST)
        if (
            schedule.scheduled_post_time
            <= observed_at + timedelta(minutes=min_lead_minutes)
        ):
            skipped += 1
            continue

        for entry in race_entries.itertuples(index=False):
            post_position = int(entry.post_position)
            item = odds_by_position[post_position]
            rows.append({
                "race_id": race_id,
                "horse_id": f"{race_id}-{post_position}",
                "horse_name": str(entry.horse_name),
                "decimal_odds": float(item.decimal_odds),
                "observed_at": observed_at.isoformat(),
                "scheduled_post_time": (
                    schedule.scheduled_post_time.isoformat()
                ),
                "source": "JRA-VAN Data Lab free trial realtime 0B31",
                "source_reference": (
                    f"dataspec={REALTIME_WIN_ODDS_DATASPEC};"
                    f"key={_race_id_to_realtime_key(race_id)};"
                    f"data_division={selected.data_division};"
                    f"published_mmddhhmm={selected.published_mmddhhmm}"
                ),
            })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.sort_values(
            ["scheduled_post_time", "race_id", "horse_id"],
            kind="stable",
        ).reset_index(drop=True)
    return frame, skipped


def write_trial_forward_summary(
    summary: TrialForwardInputSummary,
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def build_trial_forward_summary(
    *,
    status: str,
    history_cutoff: str,
    captured_at: datetime,
    decision_time: datetime | None,
    current_week_rows: int,
    current_week_races: int,
    entries: pd.DataFrame,
    odds: pd.DataFrame,
    skipped_races_no_complete_odds: int,
    schedules: dict[str, RaceSchedule],
    entries_path: str | Path | None,
    odds_path: str | Path | None,
) -> TrialForwardInputSummary:
    post_times = [
        schedules[race_id].scheduled_post_time
        for race_id in entries["race_id"].astype(str).unique().tolist()
        if race_id in schedules
    ] if not entries.empty else []

    return TrialForwardInputSummary(
        status=status,
        history_cutoff=history_cutoff,
        captured_at=captured_at.isoformat(),
        decision_time=(
            decision_time.isoformat()
            if decision_time is not None
            else None
        ),
        current_week_rows=current_week_rows,
        current_week_races=current_week_races,
        future_entry_rows=int(len(entries)),
        future_entry_races=(
            int(entries["race_id"].nunique())
            if not entries.empty
            else 0
        ),
        odds_rows=int(len(odds)),
        odds_races=(
            int(odds["race_id"].nunique())
            if not odds.empty
            else 0
        ),
        skipped_races_no_complete_odds=skipped_races_no_complete_odds,
        earliest_post_time=(
            min(post_times).isoformat()
            if post_times
            else None
        ),
        latest_post_time=(
            max(post_times).isoformat()
            if post_times
            else None
        ),
        entries_path=(
            str(entries_path)
            if entries_path is not None
            else None
        ),
        odds_path=(
            str(odds_path)
            if odds_path is not None
            else None
        ),
    )
