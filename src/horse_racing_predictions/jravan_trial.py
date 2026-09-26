from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from .current_history import (
    HistorySourceManifest,
    prepare_current_history,
)
from .data_sources import load_jra_history_csv
from .jravan import export_race_raw
from .jravan_doctor import (
    run_jravan_doctor,
    write_doctor_report,
)
from .jravan_parser import convert_raw_jsonl


@dataclass(frozen=True)
class JraVanTrialPipelineSummary:
    status: str
    base_end: str
    parsed_rows: int
    parsed_races: int
    supplemental_rows_after_base: int
    supplemental_start: str | None
    supplemental_end: str | None
    current_history_rows: int
    current_history_end: str | None
    output_dir: str
    artifact_dir: str


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


def run_jravan_trial_pipeline(
    *,
    base_path: str | Path,
    output_dir: str | Path = "data/jravan/full",
    artifact_dir: str | Path = "artifacts/jravan_full",
    from_time: str = "20210801000000",
    option: int = 4,
) -> JraVanTrialPipelineSummary:
    output_dir = Path(output_dir)
    artifact_dir = Path(artifact_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    doctor = run_jravan_doctor(
        from_time=from_time,
        option=option,
        max_records=1000,
    )
    write_doctor_report(
        doctor,
        artifact_dir / "doctor.json",
    )
    if not doctor.ready:
        raise RuntimeError(
            "JV-Link doctor did not reach ready state. "
            "See artifacts/jravan_full/doctor.json."
        )

    raw_path = output_dir / "race_raw.jsonl"
    export_race_raw(
        output_path=raw_path,
        summary_path=artifact_dir / "raw_summary.json",
        from_time=from_time,
        option=option,
        record_types={"RA", "SE"},
    )

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

    base = load_jra_history_csv(base_path)
    parsed = pd.read_csv(
        parsed_path,
        encoding="utf-8-sig",
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

    supplement_path = output_dir / "history_supplement.csv"
    supplement.to_csv(
        supplement_path,
        index=False,
        encoding="utf-8-sig",
    )

    manifest = HistorySourceManifest.create(
        source_name="JRA-VAN Data Lab free trial",
        source_kind="licensed_provider",
        source_reference=(
            f"JV-Link local trial export from_time={from_time} option={option}"
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

    current = pd.read_csv(
        current_history_path,
        encoding="utf-8-sig",
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

    summary = JraVanTrialPipelineSummary(
        status="ready",
        base_end=str(base_end.date()),
        parsed_rows=int(parse_report.output_rows),
        parsed_races=int(parse_report.output_races),
        supplemental_rows_after_base=int(len(supplement)),
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
