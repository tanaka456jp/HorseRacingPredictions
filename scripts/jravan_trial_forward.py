import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path

import pandas as pd

from horse_racing_predictions.data_sources import load_jra_history_csv
from horse_racing_predictions.jravan import export_race_raw
from horse_racing_predictions.jravan_forward import (
    JST,
    build_future_entries_from_current_week,
    build_trial_forward_summary,
    capture_complete_win_odds,
    write_trial_forward_summary,
)


def _history_cutoff(
    history_path: Path,
    history_summary_path: Path | None,
) -> str:
    if history_summary_path is not None and history_summary_path.exists():
        payload = json.loads(
            history_summary_path.read_text(encoding="utf-8")
        )
        value = str(payload.get("current_history_end", "")).strip()
        if value:
            return value

    history = load_jra_history_csv(history_path)
    if history.empty:
        raise ValueError("current history is empty")
    return str(
        pd.to_datetime(
            history["race_date"],
            errors="raise",
        ).max().date()
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare FREE-FIRST forward entries and realtime win-odds "
            "snapshots from a local JRA-VAN free-trial JV-Link runtime."
        )
    )
    parser.add_argument(
        "--history",
        default="data/jravan/full/current_history.csv",
    )
    parser.add_argument(
        "--history-summary",
        default="artifacts/jravan_full/pipeline_summary.json",
    )
    parser.add_argument(
        "--output-dir",
        default="data/jravan/forward",
    )
    parser.add_argument(
        "--artifact-dir",
        default="artifacts/jravan_forward",
    )
    parser.add_argument(
        "--min-lead-minutes",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--max-current-week-records",
        type=int,
        default=100000,
    )
    args = parser.parse_args()

    history_path = Path(args.history)
    if not history_path.exists():
        raise FileNotFoundError(history_path)
    if args.min_lead_minutes < 0:
        raise ValueError("--min-lead-minutes must be non-negative")
    if args.max_current_week_records < 1:
        raise ValueError("--max-current-week-records must be positive")

    output_dir = Path(args.output_dir)
    artifact_dir = Path(args.artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    captured_at = datetime.now(JST)
    cutoff = _history_cutoff(
        history_path,
        (
            Path(args.history_summary)
            if args.history_summary
            else None
        ),
    )

    raw_path = output_dir / "current_week_raw.jsonl"
    raw_summary_path = artifact_dir / "current_week_raw_summary.json"

    print("phase=current_week_capture start", flush=True)
    raw_summary = export_race_raw(
        output_path=raw_path,
        summary_path=raw_summary_path,
        from_time="00000000000000",
        option=2,
        record_types={"RA", "SE"},
        max_records=args.max_current_week_records,
        progress_callback=lambda message: print(message, flush=True),
    )
    if raw_summary.records_written >= args.max_current_week_records:
        raise RuntimeError(
            "current-week capture reached the safety record limit; "
            "refusing to build potentially truncated forward entries"
        )
    print(
        f"phase=current_week_capture complete records={raw_summary.records_written}",
        flush=True,
    )

    entries, schedules, source_counts = (
        build_future_entries_from_current_week(
            raw_path,
            history_cutoff=cutoff,
            now=captured_at,
            min_lead_minutes=args.min_lead_minutes,
        )
    )

    empty_odds = pd.DataFrame()
    summary_path = artifact_dir / "trial_forward_input_summary.json"

    if entries.empty:
        summary = build_trial_forward_summary(
            status="waiting_for_future_entries",
            history_cutoff=cutoff,
            captured_at=captured_at,
            decision_time=None,
            current_week_rows=source_counts["current_week_rows"],
            current_week_races=source_counts["current_week_races"],
            entries=entries,
            odds=empty_odds,
            skipped_races_no_complete_odds=0,
            schedules=schedules,
            entries_path=None,
            odds_path=None,
        )
        write_trial_forward_summary(summary, summary_path)
        print("status=waiting_for_future_entries", flush=True)
        print(summary_path)
        return

    print(
        "phase=realtime_odds start "
        f"candidate_races={entries['race_id'].nunique()}",
        flush=True,
    )
    odds, skipped = capture_complete_win_odds(
        entries,
        schedules,
        min_lead_minutes=args.min_lead_minutes,
    )
    decision_time = datetime.now(JST)

    if not odds.empty:
        post_times = pd.to_datetime(
            odds["scheduled_post_time"],
            errors="raise",
            utc=True,
        )
        threshold_utc = pd.Timestamp(
            decision_time + timedelta(minutes=args.min_lead_minutes)
        ).tz_convert("UTC")
        safe_race_ids = set(
            odds.loc[
                post_times > threshold_utc,
                "race_id",
            ].astype(str)
        )
        odds = odds.loc[
            odds["race_id"].astype(str).isin(safe_race_ids)
        ].copy()
        entries = entries.loc[
            entries["race_id"].astype(str).isin(safe_race_ids)
        ].copy()

    if odds.empty or entries.empty:
        summary = build_trial_forward_summary(
            status="waiting_for_eligible_odds",
            history_cutoff=cutoff,
            captured_at=captured_at,
            decision_time=decision_time,
            current_week_rows=source_counts["current_week_rows"],
            current_week_races=source_counts["current_week_races"],
            entries=entries,
            odds=odds,
            skipped_races_no_complete_odds=skipped,
            schedules=schedules,
            entries_path=None,
            odds_path=None,
        )
        write_trial_forward_summary(summary, summary_path)
        print("status=waiting_for_eligible_odds", flush=True)
        print(summary_path)
        return

    odds_race_ids = set(odds["race_id"].astype(str).unique())
    entries = entries.loc[
        entries["race_id"].astype(str).isin(odds_race_ids)
    ].copy()

    entries_path = output_dir / "future_entries.csv"
    odds_path = output_dir / "odds_snapshots.csv"
    entries.to_csv(
        entries_path,
        index=False,
        encoding="utf-8-sig",
    )
    odds.to_csv(
        odds_path,
        index=False,
        encoding="utf-8-sig",
    )

    summary = build_trial_forward_summary(
        status="ready",
        history_cutoff=cutoff,
        captured_at=captured_at,
        decision_time=decision_time,
        current_week_rows=source_counts["current_week_rows"],
        current_week_races=source_counts["current_week_races"],
        entries=entries,
        odds=odds,
        skipped_races_no_complete_odds=skipped,
        schedules=schedules,
        entries_path=entries_path,
        odds_path=odds_path,
    )
    write_trial_forward_summary(summary, summary_path)

    print("status=ready", flush=True)
    print(f"future_entry_rows={len(entries)}", flush=True)
    print(f"future_entry_races={entries['race_id'].nunique()}", flush=True)
    print(f"odds_rows={len(odds)}", flush=True)
    print(f"odds_races={odds['race_id'].nunique()}", flush=True)
    print(f"decision_time={decision_time.isoformat()}", flush=True)
    print(summary_path)


if __name__ == "__main__":
    main()
