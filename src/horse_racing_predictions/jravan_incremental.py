from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import timedelta
import json
import os
from pathlib import Path

import pandas as pd

from .data_sources import read_csv_flexible
from .jravan import export_race_raw
from .jravan_parser import parse_raw_jsonl
from .jravan_trial import (
    filter_single_winner_races,
    resume_current_history_from_parsed,
    write_winner_conflict_report,
)


@dataclass(frozen=True)
class IncrementalHistorySummary:
    status: str
    existing_rows: int
    existing_races: int
    existing_end: str
    requested_from_time: str
    raw_records: int
    parsed_update_rows: int
    parsed_update_races: int
    eligible_update_rows: int
    eligible_update_races: int
    replaced_races: int
    merged_rows: int
    merged_races: int
    merged_end: str
    current_history_end: str
    winner_conflict_excluded_races: int
    winner_conflict_excluded_rows: int
    output_dir: str
    artifact_dir: str


def incremental_from_time(
    existing: pd.DataFrame,
    *,
    overlap_days: int = 7,
) -> str:
    if overlap_days < 0:
        raise ValueError("overlap_days must be non-negative")
    if existing.empty:
        raise ValueError("existing parsed history is empty")
    if "race_date" not in existing.columns:
        raise ValueError("existing parsed history lacks race_date")

    dates = pd.to_datetime(
        existing["race_date"],
        errors="raise",
    )
    latest = dates.max().normalize()
    start = latest - timedelta(days=overlap_days)
    return start.strftime("%Y%m%d000000")


def merge_completed_increment(
    existing: pd.DataFrame,
    update: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    if existing.empty:
        raise ValueError("existing parsed history is empty")
    if update.empty:
        return existing.copy(), 0

    required = {
        "race_id",
        "race_date",
        "post_position",
        "finish_position",
    }
    for name, frame in (
        ("existing", existing),
        ("update", update),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(
                f"{name} parsed history missing columns: {sorted(missing)}"
            )

    update_races = set(update["race_id"].astype(str))
    kept = existing.loc[
        ~existing["race_id"].astype(str).isin(update_races)
    ].copy()
    merged = pd.concat(
        [kept, update],
        ignore_index=True,
        sort=False,
    )
    merged["race_date"] = pd.to_datetime(
        merged["race_date"],
        errors="raise",
    )
    merged = merged.sort_values(
        ["race_date", "race_id", "post_position"],
        kind="stable",
    ).reset_index(drop=True)
    return merged, len(update_races)


def _atomic_write_csv(
    frame: pd.DataFrame,
    path: Path,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".next")
    frame.to_csv(
        temp,
        index=False,
        encoding="utf-8-sig",
    )
    os.replace(temp, path)


def run_incremental_history_update(
    *,
    parsed_path: str | Path = "data/jravan/full/parsed_history.csv",
    base_path: str | Path | None = None,
    output_dir: str | Path = "data/jravan/full",
    artifact_dir: str | Path = "artifacts/jravan_incremental",
    overlap_days: int = 7,
) -> IncrementalHistorySummary:
    parsed_path = Path(parsed_path)
    output_dir = Path(output_dir)
    artifact_dir = Path(artifact_dir)
    if not parsed_path.exists():
        raise FileNotFoundError(parsed_path)

    existing = read_csv_flexible(
        parsed_path,
        low_memory=False,
    )
    if existing.empty:
        raise ValueError("existing parsed_history.csv is empty")

    existing_dates = pd.to_datetime(
        existing["race_date"],
        errors="raise",
    )
    existing_end = existing_dates.max().normalize()
    from_time = incremental_from_time(
        existing,
        overlap_days=overlap_days,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    raw_path = output_dir / "incremental_raw.jsonl"
    raw_summary_path = artifact_dir / "raw_summary.json"
    raw_summary = export_race_raw(
        output_path=raw_path,
        summary_path=raw_summary_path,
        from_time=from_time,
        option=1,
        record_types={"RA", "SE"},
        progress_callback=lambda message: print(message, flush=True),
    )

    update, parse_report = parse_raw_jsonl(
        raw_path,
        completed_only=True,
    )

    if update.empty:
        current_summary = resume_current_history_from_parsed(
            base_path=base_path,
            output_dir=output_dir,
            artifact_dir=artifact_dir / "current_history",
        )
        summary = IncrementalHistorySummary(
            status="no_completed_updates",
            existing_rows=int(len(existing)),
            existing_races=int(existing["race_id"].nunique()),
            existing_end=str(existing_end.date()),
            requested_from_time=from_time,
            raw_records=int(raw_summary.records_written),
            parsed_update_rows=0,
            parsed_update_races=0,
            eligible_update_rows=0,
            eligible_update_races=0,
            replaced_races=0,
            merged_rows=int(len(existing)),
            merged_races=int(existing["race_id"].nunique()),
            merged_end=str(existing_end.date()),
            current_history_end=str(current_summary.current_history_end),
            winner_conflict_excluded_races=0,
            winner_conflict_excluded_rows=0,
            output_dir=str(output_dir),
            artifact_dir=str(artifact_dir),
        )
        (artifact_dir / "incremental_summary.json").write_text(
            json.dumps(asdict(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    eligible, winner_filter = filter_single_winner_races(update)
    write_winner_conflict_report(
        winner_filter,
        artifact_dir / "winner_conflict_filter.json",
    )

    if eligible.empty:
        current_summary = resume_current_history_from_parsed(
            base_path=base_path,
            output_dir=output_dir,
            artifact_dir=artifact_dir / "current_history",
        )
        summary = IncrementalHistorySummary(
            status="no_eligible_completed_updates",
            existing_rows=int(len(existing)),
            existing_races=int(existing["race_id"].nunique()),
            existing_end=str(existing_end.date()),
            requested_from_time=from_time,
            raw_records=int(raw_summary.records_written),
            parsed_update_rows=int(parse_report.output_rows),
            parsed_update_races=int(parse_report.output_races),
            eligible_update_rows=0,
            eligible_update_races=0,
            replaced_races=0,
            merged_rows=int(len(existing)),
            merged_races=int(existing["race_id"].nunique()),
            merged_end=str(existing_end.date()),
            current_history_end=str(current_summary.current_history_end),
            winner_conflict_excluded_races=winner_filter.excluded_races,
            winner_conflict_excluded_rows=winner_filter.excluded_rows,
            output_dir=str(output_dir),
            artifact_dir=str(artifact_dir),
        )
        (artifact_dir / "incremental_summary.json").write_text(
            json.dumps(asdict(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return summary

    # Guard against replacing a race with a visibly partial snapshot.
    counts = eligible.groupby("race_id").size()
    eligible_race_ids = set(
        str(value)
        for value in counts.index[counts.ge(2)].tolist()
    )
    eligible = eligible.loc[
        eligible["race_id"].astype(str).isin(eligible_race_ids)
    ].copy()
    if eligible.empty:
        raise RuntimeError(
            "incremental data had no safely complete multi-runner races"
        )

    merged, replaced_races = merge_completed_increment(
        existing,
        eligible,
    )
    merged_dates = pd.to_datetime(
        merged["race_date"],
        errors="raise",
    )
    merged_end = merged_dates.max().normalize()
    if merged_end < existing_end:
        raise RuntimeError(
            "incremental merge would regress parsed history end date"
        )

    _atomic_write_csv(
        merged,
        parsed_path,
    )

    current_summary = resume_current_history_from_parsed(
        base_path=base_path,
        output_dir=output_dir,
        artifact_dir=artifact_dir / "current_history",
    )

    status = (
        "updated"
        if merged_end > existing_end
        else "refreshed_overlap_only"
    )
    summary = IncrementalHistorySummary(
        status=status,
        existing_rows=int(len(existing)),
        existing_races=int(existing["race_id"].nunique()),
        existing_end=str(existing_end.date()),
        requested_from_time=from_time,
        raw_records=int(raw_summary.records_written),
        parsed_update_rows=int(parse_report.output_rows),
        parsed_update_races=int(parse_report.output_races),
        eligible_update_rows=int(len(eligible)),
        eligible_update_races=int(eligible["race_id"].nunique()),
        replaced_races=int(replaced_races),
        merged_rows=int(len(merged)),
        merged_races=int(merged["race_id"].nunique()),
        merged_end=str(merged_end.date()),
        current_history_end=str(current_summary.current_history_end),
        winner_conflict_excluded_races=winner_filter.excluded_races,
        winner_conflict_excluded_rows=winner_filter.excluded_rows,
        output_dir=str(output_dir),
        artifact_dir=str(artifact_dir),
    )
    (artifact_dir / "incremental_summary.json").write_text(
        json.dumps(asdict(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary
