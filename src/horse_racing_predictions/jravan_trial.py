from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Callable

import pandas as pd

from .current_history import (
    HistorySourceManifest,
    prepare_current_history,
)
from .data_sources import (
    load_jra_history_csv,
    read_csv_flexible,
)
from .jravan import JraVanApiError, export_race_raw
from .jravan_parser import convert_raw_jsonl


DATASET_HANDLE = "takamotoki/jra-horse-racing-dataset"
RACE_RESULT_FILE = "19860105-20210731_race_result.csv"


def resolve_approved_base_history(
    base_path: str | Path | None = None,
    *,
    cache_dir: str | Path = "data/raw",
) -> Path:
    if base_path is not None:
        path = Path(base_path)
        if not path.exists():
            raise FileNotFoundError(path)
        return path

    try:
        import kagglehub
    except ImportError as exc:
        raise RuntimeError(
            "Automatic base-history download requires kagglehub. "
            "Install requirements-jravan.txt."
        ) from exc

    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded = kagglehub.dataset_download(
        DATASET_HANDLE,
        path=RACE_RESULT_FILE,
        output_dir=str(cache_dir),
    )
    path = Path(downloaded)
    if path.is_file():
        return path

    direct = path / RACE_RESULT_FILE
    if direct.exists():
        return direct

    matches = list(path.rglob(RACE_RESULT_FILE))
    if len(matches) != 1:
        raise FileNotFoundError(
            f"could not uniquely locate {RACE_RESULT_FILE}: {matches}"
        )
    return matches[0]


@dataclass(frozen=True)
class WinnerConflictFilterReport:
    total_races: int
    total_rows: int
    kept_races: int
    kept_rows: int
    zero_winner_races: int
    multiple_winner_races: int
    excluded_races: int
    excluded_rows: int
    zero_winner_race_ids: tuple[str, ...]
    multiple_winner_race_ids: tuple[str, ...]


@dataclass(frozen=True)
class JraVanTrialPipelineSummary:
    status: str
    acquisition_mode: str
    requested_from_time: str
    effective_from_time: str
    effective_option: int
    fallback_reason: str | None
    history_gap_days: int | None
    base_end: str
    parsed_rows: int
    parsed_races: int
    supplemental_rows_after_base: int
    winner_conflict_excluded_races: int
    winner_conflict_excluded_rows: int
    zero_winner_races: int
    multiple_winner_races: int
    supplemental_start: str | None
    supplemental_end: str | None
    current_history_rows: int
    current_history_end: str | None
    output_dir: str
    artifact_dir: str




def recent_normal_from_time(
    *,
    now: datetime | None = None,
    days: int = 365,
) -> str:
    if days < 1:
        raise ValueError("days must be positive")
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    start = (now - timedelta(days=days)).astimezone(timezone.utc)
    return start.strftime("%Y%m%d000000")


def acquire_trial_race_raw(
    *,
    output_path: str | Path,
    summary_path: str | Path,
    setup_from_time: str,
    setup_option: int = 4,
    recent_days: int = 365,
    now: datetime | None = None,
    exporter=export_race_raw,
    progress_callback: Callable[[str], None] | None = None,
):
    try:
        if progress_callback is not None:
            progress_callback(
                "acquisition_attempt=setup_full "
                f"from_time={setup_from_time} option={setup_option}"
            )
        summary = exporter(
            output_path=output_path,
            summary_path=summary_path,
            from_time=setup_from_time,
            option=setup_option,
            record_types={"RA", "SE"},
            progress_callback=progress_callback,
        )
        return (
            summary,
            "setup_full",
            setup_from_time,
            setup_option,
            None,
        )
    except JraVanApiError as exc:
        message = str(exc)
        if "return code -301" not in message:
            raise

        fallback_from = recent_normal_from_time(
            now=now,
            days=recent_days,
        )
        if progress_callback is not None:
            progress_callback(
                "setup_full_blocked=-301; "
                "switching_to=recent_normal_fallback "
                f"from_time={fallback_from} option=1"
            )
        summary = exporter(
            output_path=output_path,
            summary_path=summary_path,
            from_time=fallback_from,
            option=1,
            record_types={"RA", "SE"},
            progress_callback=progress_callback,
        )
        return (
            summary,
            "recent_normal_fallback",
            fallback_from,
            1,
            (
                "setup JVOpen returned -301 authentication error; "
                "fell back to normal data (option=1) for the recent "
                f"{recent_days}-day window"
            ),
        )


def filter_after_base_history(
    base: pd.DataFrame,
    parsed: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.Timestamp]:
    if base.empty:
        raise ValueError("base history is empty")
    if parsed.empty:
        raise ValueError("parsed JRA-VAN history is empty")

    base_dates = pd.to_datetime(
        base["race_date"],
        errors="raise",
    )
    parsed = parsed.copy()
    parsed["race_date"] = pd.to_datetime(
        parsed["race_date"],
        errors="raise",
    )

    base_end = base_dates.max().normalize()
    supplement = parsed.loc[
        parsed["race_date"].dt.normalize() > base_end
    ].copy()
    supplement = supplement.sort_values(
        ["race_date", "race_id", "post_position"],
        kind="stable",
    ).reset_index(drop=True)
    return supplement, base_end




def filter_single_winner_races(
    frame: pd.DataFrame,
) -> tuple[pd.DataFrame, WinnerConflictFilterReport]:
    if frame.empty:
        raise ValueError("supplemental history is empty")

    finish = pd.to_numeric(
        frame["finish_position"],
        errors="coerce",
    )
    winner_counts = (
        frame.assign(_winner=finish.eq(1).astype(int))
        .groupby("race_id", dropna=False)["_winner"]
        .sum()
    )

    zero_ids = tuple(
        str(value)
        for value in winner_counts.index[winner_counts.eq(0)].tolist()
    )
    multiple_ids = tuple(
        str(value)
        for value in winner_counts.index[winner_counts.gt(1)].tolist()
    )
    excluded_ids = set(zero_ids) | set(multiple_ids)

    race_id_text = frame["race_id"].astype(str)
    keep_mask = ~race_id_text.isin(excluded_ids)
    kept = frame.loc[keep_mask].copy().reset_index(drop=True)

    report = WinnerConflictFilterReport(
        total_races=int(winner_counts.size),
        total_rows=int(len(frame)),
        kept_races=int(kept["race_id"].nunique()),
        kept_rows=int(len(kept)),
        zero_winner_races=len(zero_ids),
        multiple_winner_races=len(multiple_ids),
        excluded_races=len(excluded_ids),
        excluded_rows=int((~keep_mask).sum()),
        zero_winner_race_ids=zero_ids,
        multiple_winner_race_ids=multiple_ids,
    )
    return kept, report


def write_winner_conflict_report(
    report: WinnerConflictFilterReport,
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def run_jravan_trial_pipeline(
    *,
    base_path: str | Path | None = None,
    output_dir: str | Path = "data/jravan/full",
    artifact_dir: str | Path = "artifacts/jravan_full",
    from_time: str = "20210801000000",
    option: int = 4,
) -> JraVanTrialPipelineSummary:
    def progress(message: str) -> None:
        print(message, flush=True)

    progress("phase=resolve_base_history start")
    base_path = resolve_approved_base_history(base_path)
    progress(
        "phase=resolve_base_history complete "
        f"path={base_path}"
    )
    output_dir = Path(output_dir)
    artifact_dir = Path(artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    progress("phase=acquire_jravan start")
    raw_path = output_dir / "race_raw.jsonl"
    (
        _raw_summary,
        acquisition_mode,
        effective_from_time,
        effective_option,
        fallback_reason,
    ) = acquire_trial_race_raw(
        output_path=raw_path,
        summary_path=artifact_dir / "raw_summary.json",
        setup_from_time=from_time,
        setup_option=option,
        progress_callback=progress,
    )
    progress(
        "phase=acquire_jravan complete "
        f"mode={acquisition_mode}"
    )

    progress("phase=parse_history start")
    parsed_path = output_dir / "parsed_history.csv"
    parse_report = convert_raw_jsonl(
        input_path=raw_path,
        output_path=parsed_path,
        report_path=artifact_dir / "parse_report.json",
    )
    if parse_report.output_rows == 0:
        raise RuntimeError(
            "No completed RA/SE history rows were parsed."
        )
    progress(
        "phase=parse_history complete "
        f"rows={parse_report.output_rows} "
        f"races={parse_report.output_races}"
    )

    progress("phase=current_history_intake start")
    base = load_jra_history_csv(base_path)
    parsed = read_csv_flexible(
        parsed_path,
        low_memory=False,
    )
    supplement, base_end = filter_after_base_history(
        base,
        parsed,
    )
    if supplement.empty:
        raise RuntimeError(
            "JRA-VAN data contains no completed races after "
            f"base history end {base_end.date()}."
        )

    supplement, winner_filter = filter_single_winner_races(
        supplement
    )
    write_winner_conflict_report(
        winner_filter,
        artifact_dir / "winner_conflict_filter.json",
    )
    progress(
        "winner_filter "
        f"excluded_races={winner_filter.excluded_races} "
        f"zero_winner={winner_filter.zero_winner_races} "
        f"multiple_winner={winner_filter.multiple_winner_races} "
        f"excluded_rows={winner_filter.excluded_rows}"
    )
    if supplement.empty:
        raise RuntimeError(
            "No single-winner races remain after winner-conflict filtering."
        )

    supplement_path = output_dir / "history_supplement.csv"
    supplement.to_csv(
        supplement_path,
        index=False,
        encoding="utf-8-sig",
    )

    manifest = HistorySourceManifest.create(
        source_name=(
            "JRA-VAN Data Lab free trial"
            if acquisition_mode == "setup_full"
            else "JRA-VAN Data Lab free trial recent normal data"
        ),
        source_kind="licensed_provider",
        source_reference=(
            "JV-Link local trial export "
            f"requested_from_time={from_time} requested_option={option} "
            f"effective_from_time={effective_from_time} "
            f"effective_option={effective_option} "
            f"mode={acquisition_mode}"
        ),
        rights_note=(
            "Acquired locally through official JRA-VAN Data Lab/JV-Link. "
            "Raw redistribution is disabled."
        ),
        approved_for_modeling=True,
        raw_redistribution_allowed=False,
        acquired_at=datetime.now(timezone.utc),
    )

    current_history_path = output_dir / "current_history.csv"
    intake = prepare_current_history(
        base_path=base_path,
        supplemental_path=supplement_path,
        output_path=current_history_path,
        manifest_path=artifact_dir / "source_manifest.json",
        report_path=artifact_dir / "intake_report.json",
        manifest=manifest,
        max_gap_days=14,
        allow_gap=True,
    )
    if not intake.ready:
        raise RuntimeError(
            "Current History Intake blocked the JRA-VAN supplement: "
            + "; ".join(intake.errors)
        )
    progress(
        "phase=current_history_intake complete "
        f"merged_rows={intake.merged_rows}"
    )

    current = read_csv_flexible(
        current_history_path,
        low_memory=False,
    )
    current_dates = pd.to_datetime(
        current["race_date"],
        errors="raise",
    )

    supplement_start = pd.to_datetime(
        supplement["race_date"],
        errors="raise",
    ).min()
    supplement_end = pd.to_datetime(
        supplement["race_date"],
        errors="raise",
    ).max()

    gap_days = int(
        (
            pd.to_datetime(supplement_start).normalize()
            - base_end.normalize()
        ).days
    )

    summary = JraVanTrialPipelineSummary(
        status=(
            "ready"
            if acquisition_mode == "setup_full"
            else "ready_recent_history_gap"
        ),
        acquisition_mode=acquisition_mode,
        requested_from_time=from_time,
        effective_from_time=effective_from_time,
        effective_option=effective_option,
        fallback_reason=fallback_reason,
        history_gap_days=gap_days,
        base_end=str(base_end.date()),
        parsed_rows=int(parse_report.output_rows),
        parsed_races=int(parse_report.output_races),
        supplemental_rows_after_base=int(len(supplement)),
        winner_conflict_excluded_races=winner_filter.excluded_races,
        winner_conflict_excluded_rows=winner_filter.excluded_rows,
        zero_winner_races=winner_filter.zero_winner_races,
        multiple_winner_races=winner_filter.multiple_winner_races,
        supplemental_start=str(supplement_start.date()),
        supplemental_end=str(supplement_end.date()),
        current_history_rows=int(len(current)),
        current_history_end=str(
            current_dates.max().date()
        ),
        output_dir=str(output_dir),
        artifact_dir=str(artifact_dir),
    )
    (artifact_dir / "pipeline_summary.json").write_text(
        json.dumps(
            asdict(summary),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary


def resume_current_history_from_parsed(
    *,
    base_path: str | Path | None = None,
    output_dir: str | Path = "data/jravan/full",
    artifact_dir: str | Path = "artifacts/jravan_full",
) -> JraVanTrialPipelineSummary:
    def progress(message: str) -> None:
        print(message, flush=True)

    output_dir = Path(output_dir)
    artifact_dir = Path(artifact_dir)
    parsed_path = output_dir / "parsed_history.csv"
    raw_path = output_dir / "race_raw.jsonl"

    if not parsed_path.exists():
        raise FileNotFoundError(
            "parsed_history.csv does not exist; a completed acquisition/"
            "parse run is required before resume"
        )

    progress("resume=existing_parsed_history")
    progress("phase=resolve_base_history start")
    base_path = resolve_approved_base_history(base_path)
    progress(
        "phase=resolve_base_history complete "
        f"path={base_path}"
    )

    progress("phase=current_history_intake start")
    base = load_jra_history_csv(base_path)
    parsed = read_csv_flexible(
        parsed_path,
        low_memory=False,
    )
    supplement, base_end = filter_after_base_history(
        base,
        parsed,
    )
    if supplement.empty:
        raise RuntimeError(
            "Existing parsed JRA-VAN data contains no completed races after "
            f"base history end {base_end.date()}."
        )

    supplement, winner_filter = filter_single_winner_races(
        supplement
    )
    write_winner_conflict_report(
        winner_filter,
        artifact_dir / "winner_conflict_filter.json",
    )
    progress(
        "winner_filter "
        f"excluded_races={winner_filter.excluded_races} "
        f"zero_winner={winner_filter.zero_winner_races} "
        f"multiple_winner={winner_filter.multiple_winner_races} "
        f"excluded_rows={winner_filter.excluded_rows}"
    )
    if supplement.empty:
        raise RuntimeError(
            "No single-winner races remain after winner-conflict filtering."
        )

    supplement_path = output_dir / "history_supplement.csv"
    supplement.to_csv(
        supplement_path,
        index=False,
        encoding="utf-8-sig",
    )

    manifest = HistorySourceManifest.create(
        source_name="JRA-VAN Data Lab free trial recovered local history",
        source_kind="licensed_provider",
        source_reference=(
            "Recovered from existing local parsed_history.csv after a "
            "completed JV-Link acquisition; raw redistribution disabled."
        ),
        rights_note=(
            "Acquired locally through official JRA-VAN Data Lab/JV-Link. "
            "This resume path reuses already-downloaded local data."
        ),
        approved_for_modeling=True,
        raw_redistribution_allowed=False,
        acquired_at=datetime.now(timezone.utc),
    )

    current_history_path = output_dir / "current_history.csv"
    intake = prepare_current_history(
        base_path=base_path,
        supplemental_path=supplement_path,
        output_path=current_history_path,
        manifest_path=artifact_dir / "source_manifest.json",
        report_path=artifact_dir / "intake_report.json",
        manifest=manifest,
        max_gap_days=14,
        allow_gap=True,
    )
    if not intake.ready:
        raise RuntimeError(
            "Current History Intake blocked resumed JRA-VAN data: "
            + "; ".join(intake.errors)
        )

    current = read_csv_flexible(
        current_history_path,
        low_memory=False,
    )
    current_dates = pd.to_datetime(
        current["race_date"],
        errors="raise",
    )

    supplement_dates = pd.to_datetime(
        supplement["race_date"],
        errors="raise",
    )
    supplement_start = supplement_dates.min()
    supplement_end = supplement_dates.max()
    gap_days = int(
        (
            supplement_start.normalize()
            - base_end.normalize()
        ).days
    )

    progress(
        "phase=current_history_intake complete "
        f"merged_rows={intake.merged_rows}"
    )

    summary = JraVanTrialPipelineSummary(
        status="ready_recent_history_gap",
        acquisition_mode="resume_existing_parsed",
        requested_from_time="",
        effective_from_time="",
        effective_option=0,
        fallback_reason=(
            "Resumed from local parsed_history.csv; no JV-Link reacquisition "
            "was performed."
        ),
        history_gap_days=gap_days,
        base_end=str(base_end.date()),
        parsed_rows=int(len(parsed)),
        parsed_races=int(parsed["race_id"].nunique()),
        supplemental_rows_after_base=int(len(supplement)),
        winner_conflict_excluded_races=winner_filter.excluded_races,
        winner_conflict_excluded_rows=winner_filter.excluded_rows,
        zero_winner_races=winner_filter.zero_winner_races,
        multiple_winner_races=winner_filter.multiple_winner_races,
        supplemental_start=str(supplement_start.date()),
        supplemental_end=str(supplement_end.date()),
        current_history_rows=int(len(current)),
        current_history_end=str(current_dates.max().date()),
        output_dir=str(output_dir),
        artifact_dir=str(artifact_dir),
    )
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "pipeline_summary.json").write_text(
        json.dumps(
            asdict(summary),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return summary
