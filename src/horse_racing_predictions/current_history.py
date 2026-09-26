from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

import pandas as pd

from .data_sources import load_jra_history_csv


SourceKind = Literal[
    "user_supplied",
    "approved_free_provider",
    "licensed_provider",
]


@dataclass(frozen=True)
class HistorySourceManifest:
    source_name: str
    source_kind: SourceKind
    source_reference: str
    rights_note: str
    acquired_at: str
    approved_for_modeling: bool
    raw_redistribution_allowed: bool = False

    @classmethod
    def create(
        cls,
        *,
        source_name: str,
        source_kind: SourceKind,
        source_reference: str,
        rights_note: str,
        approved_for_modeling: bool,
        raw_redistribution_allowed: bool = False,
        acquired_at: datetime | None = None,
    ) -> "HistorySourceManifest":
        acquired_at = acquired_at or datetime.now(timezone.utc)
        if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
            raise ValueError("acquired_at must be timezone-aware")
        if not source_name.strip():
            raise ValueError("source_name must not be empty")
        if not rights_note.strip():
            raise ValueError("rights_note must not be empty")
        return cls(
            source_name=source_name.strip(),
            source_kind=source_kind,
            source_reference=source_reference.strip(),
            rights_note=rights_note.strip(),
            acquired_at=acquired_at.isoformat(),
            approved_for_modeling=bool(approved_for_modeling),
            raw_redistribution_allowed=bool(raw_redistribution_allowed),
        )


@dataclass(frozen=True)
class HistoryIntakeReport:
    status: str
    base_rows: int
    supplemental_rows: int
    merged_rows: int
    base_end: str | None
    supplemental_start: str | None
    supplemental_end: str | None
    gap_days: int | None
    duplicate_keys: int
    overlapping_keys: int
    invalid_result_rows: int
    invalid_odds_rows: int
    race_date_conflicts: int
    winner_count_conflicts: int
    approved_for_modeling: bool
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status == "ready"


def _row_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["race_id"].astype(str)
        + "|"
        + frame["horse_name"].astype(str)
    )


def _date_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(pd.Timestamp(value).date())


def validate_history_intake(
    base: pd.DataFrame,
    supplemental: pd.DataFrame,
    manifest: HistorySourceManifest,
    *,
    max_gap_days: int = 14,
    allow_gap: bool = False,
) -> HistoryIntakeReport:
    if max_gap_days < 0:
        raise ValueError("max_gap_days must be non-negative")

    base = base.copy()
    supplemental = supplemental.copy()

    warnings: list[str] = []
    errors: list[str] = []

    if base.empty:
        errors.append("base history is empty")
    if supplemental.empty:
        errors.append("supplemental history is empty")

    base_dates = pd.to_datetime(
        base.get("race_date"),
        errors="coerce",
    )
    supplemental_dates = pd.to_datetime(
        supplemental.get("race_date"),
        errors="coerce",
    )

    base_end = (
        base_dates.max()
        if len(base_dates) and base_dates.notna().any()
        else None
    )
    supplemental_start = (
        supplemental_dates.min()
        if len(supplemental_dates)
        and supplemental_dates.notna().any()
        else None
    )
    supplemental_end = (
        supplemental_dates.max()
        if len(supplemental_dates)
        and supplemental_dates.notna().any()
        else None
    )

    gap_days = None
    if base_end is not None and supplemental_start is not None:
        gap_days = int(
            (
                supplemental_start.normalize()
                - base_end.normalize()
            ).days
        )
        if gap_days <= 0:
            errors.append(
                "supplemental history must start after the base history"
            )
        elif gap_days > max_gap_days:
            message = (
                f"history gap is {gap_days} days, exceeding "
                f"max_gap_days={max_gap_days}"
            )
            if allow_gap:
                warnings.append(message)
            else:
                errors.append(message)

    supplemental_keys = _row_key(supplemental)
    duplicate_keys = int(supplemental_keys.duplicated().sum())
    if duplicate_keys:
        errors.append(
            f"supplemental history has {duplicate_keys} duplicate race/horse keys"
        )

    base_key_set = set(_row_key(base).tolist())
    overlapping_keys = int(
        supplemental_keys.isin(base_key_set).sum()
    )
    if overlapping_keys:
        errors.append(
            f"supplemental history overlaps {overlapping_keys} base race/horse keys"
        )

    finish = pd.to_numeric(
        supplemental.get("finish_position"),
        errors="coerce",
    )
    invalid_result_rows = int(
        finish.isna().sum()
        + finish.notna().mul(finish.lt(1)).sum()
    )
    if invalid_result_rows:
        errors.append(
            f"supplemental history has {invalid_result_rows} invalid result rows"
        )

    odds = pd.to_numeric(
        supplemental.get("win_odds"),
        errors="coerce",
    )
    invalid_odds_rows = int(
        odds.isna().sum()
        + odds.notna().mul(odds.le(1.0)).sum()
    )
    if invalid_odds_rows:
        errors.append(
            f"supplemental history has {invalid_odds_rows} invalid win-odds rows"
        )

    race_date_counts = (
        supplemental.assign(
            _race_day=pd.to_datetime(
                supplemental["race_date"],
                errors="coerce",
            ).dt.normalize()
        )
        .groupby("race_id", dropna=False)["_race_day"]
        .nunique(dropna=False)
    )
    race_date_conflicts = int(
        race_date_counts.gt(1).sum()
    )
    if race_date_conflicts:
        errors.append(
            f"{race_date_conflicts} races contain conflicting race dates"
        )

    winners = supplemental.assign(
        _winner=finish.eq(1).astype(int)
    ).groupby("race_id", dropna=False)["_winner"].sum()
    winner_count_conflicts = int(
        winners.ne(1).sum()
    )
    if winner_count_conflicts:
        errors.append(
            f"{winner_count_conflicts} races do not contain exactly one winner"
        )

    if not manifest.approved_for_modeling:
        errors.append(
            "source manifest is not approved_for_modeling"
        )

    if manifest.raw_redistribution_allowed is False:
        warnings.append(
            "raw supplemental data must not be committed or redistributed"
        )

    status = "ready" if not errors else "blocked"
    merged_rows = (
        len(base) + len(supplemental)
        if status == "ready"
        else 0
    )

    return HistoryIntakeReport(
        status=status,
        base_rows=int(len(base)),
        supplemental_rows=int(len(supplemental)),
        merged_rows=int(merged_rows),
        base_end=_date_text(base_end),
        supplemental_start=_date_text(supplemental_start),
        supplemental_end=_date_text(supplemental_end),
        gap_days=gap_days,
        duplicate_keys=duplicate_keys,
        overlapping_keys=overlapping_keys,
        invalid_result_rows=invalid_result_rows,
        invalid_odds_rows=invalid_odds_rows,
        race_date_conflicts=race_date_conflicts,
        winner_count_conflicts=winner_count_conflicts,
        approved_for_modeling=manifest.approved_for_modeling,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def merge_history(
    base: pd.DataFrame,
    supplemental: pd.DataFrame,
    manifest: HistorySourceManifest,
    report: HistoryIntakeReport,
) -> pd.DataFrame:
    if not report.ready:
        raise ValueError(
            "history intake is blocked: "
            + "; ".join(report.errors)
        )

    base = base.copy()
    supplemental = supplemental.copy()

    base["_source_name"] = base.get(
        "_source_name",
        "historical_base",
    )
    base["_source_kind"] = base.get(
        "_source_kind",
        "historical_research",
    )
    base["_source_reference"] = base.get(
        "_source_reference",
        "",
    )
    base["_source_acquired_at"] = base.get(
        "_source_acquired_at",
        "",
    )

    supplemental["_source_name"] = manifest.source_name
    supplemental["_source_kind"] = manifest.source_kind
    supplemental["_source_reference"] = manifest.source_reference
    supplemental["_source_acquired_at"] = manifest.acquired_at

    merged = pd.concat(
        [base, supplemental],
        ignore_index=True,
        sort=False,
    )
    merged["race_date"] = pd.to_datetime(
        merged["race_date"],
        errors="raise",
    )
    merged = merged.sort_values(
        ["race_date", "race_id", "horse_name"],
        kind="stable",
    ).reset_index(drop=True)
    return merged


def prepare_current_history(
    *,
    base_path: str | Path,
    supplemental_path: str | Path,
    output_path: str | Path,
    manifest_path: str | Path,
    report_path: str | Path,
    manifest: HistorySourceManifest,
    max_gap_days: int = 14,
    allow_gap: bool = False,
) -> HistoryIntakeReport:
    base = load_jra_history_csv(base_path)
    supplemental = load_jra_history_csv(
        supplemental_path
    )

    report = validate_history_intake(
        base,
        supplemental,
        manifest,
        max_gap_days=max_gap_days,
        allow_gap=allow_gap,
    )

    manifest_path = Path(manifest_path)
    report_path = Path(report_path)
    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manifest_path.write_text(
        json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    report_path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if not report.ready:
        return report

    merged = merge_history(
        base,
        supplemental,
        manifest,
        report,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    merged.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )
    return report
