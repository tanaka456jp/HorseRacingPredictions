"""Fail-closed bounded JV-Link acquisition for Phase 11 pre-2025 research.

This module exists to prevent the generic JRA-VAN history path from reading the
protected 2025-2026 final holdout. It never falls back to an unbounded/current
JVOpen request.

The caller must separately establish that the local JV-Link entitlement is
zero-cost (for example, an active official free trial) and that personal
research use is permitted. Raw JV-Data remains local and must not be committed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Callable

from .jravan import JvExportSummary, export_race_raw


PHASE11_MIN_START = "20170101000000"
PHASE11_MAX_CALENDAR_END = "20241231235959"
# JV-Link setup-data ranges may use 99-filled pseudo timestamps so that
# late-year files whose provider timestamp is not a real wall-clock instant
# are included.  This sentinel stays wholly inside provider year 2024 and
# must never be replaced by a 2025 boundary in Phase 11.
PHASE11_SAFE_SETUP_END = "20249999999999"
PHASE11_RECORD_TYPES = frozenset({"RA", "SE"})
_RANGE_RE = re.compile(r"^(\d{14})-(\d{14})$")


@dataclass(frozen=True)
class Phase11BoundedAcquisitionPlan:
    jvopen_range: str
    start: str
    end: str
    end_kind: str
    option: int
    record_types: tuple[str, ...]
    protected_holdout: str
    paid_data_allowed: bool
    unbounded_fallback_allowed: bool
    raw_redistribution_allowed: bool


def _parse_stamp(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise ValueError(
            "JVOpen bound must be a real YYYYMMDDhhmmss timestamp"
        ) from exc


def validate_phase11_jvopen_range(value: str) -> tuple[str, str]:
    """Validate a provider-side bounded setup range before any JV-Link call."""
    if not isinstance(value, str):
        raise ValueError("JVOpen range must be a string")
    match = _RANGE_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(
            "Phase 11 JVOpen requires START-END with two 14-digit timestamps"
        )

    start, end = match.groups()
    start_dt = _parse_stamp(start)
    minimum_dt = _parse_stamp(PHASE11_MIN_START)
    maximum_calendar_dt = _parse_stamp(PHASE11_MAX_CALENDAR_END)

    if start_dt < minimum_dt:
        raise ValueError(
            f"Phase 11 start must be >= {PHASE11_MIN_START}"
        )
    if end == PHASE11_SAFE_SETUP_END:
        end_dt = maximum_calendar_dt
    else:
        end_dt = _parse_stamp(end)
        if end_dt > maximum_calendar_dt:
            raise ValueError(
                "Phase 11 end must be <= "
                f"{PHASE11_MAX_CALENDAR_END} or equal the approved "
                f"2024 setup sentinel {PHASE11_SAFE_SETUP_END}"
            )
    if start_dt > end_dt:
        raise ValueError("Phase 11 JVOpen start must not be after end")

    return start, end


def build_phase11_bounded_plan(
    jvopen_range: str,
) -> Phase11BoundedAcquisitionPlan:
    start, end = validate_phase11_jvopen_range(jvopen_range)
    return Phase11BoundedAcquisitionPlan(
        jvopen_range=f"{start}-{end}",
        start=start,
        end=end,
        end_kind=(
            "provider_year_setup_sentinel"
            if end == PHASE11_SAFE_SETUP_END
            else "calendar_timestamp"
        ),
        option=4,
        record_types=tuple(sorted(PHASE11_RECORD_TYPES)),
        protected_holdout="2025-2026 untouched",
        paid_data_allowed=False,
        unbounded_fallback_allowed=False,
        raw_redistribution_allowed=False,
    )


def write_phase11_bounded_plan(
    plan: Phase11BoundedAcquisitionPlan,
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(plan),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def export_phase11_bounded_history(
    *,
    jvopen_range: str,
    output_path: str | Path,
    summary_path: str | Path,
    zero_cost_entitlement_confirmed: bool = False,
    personal_research_rights_confirmed: bool = False,
    exporter: Callable[..., JvExportSummary] = export_race_raw,
    progress_callback: Callable[[str], None] | None = None,
) -> JvExportSummary:
    """Export only bounded RA/SE setup data after explicit local entitlement gates.

    No fallback is permitted. In particular, a -301/authentication error must
    propagate instead of switching to option=1 or any current/recent window.
    """
    plan = build_phase11_bounded_plan(jvopen_range)

    if zero_cost_entitlement_confirmed is not True:
        raise RuntimeError(
            "Phase 11 bounded JV-Link acquisition requires explicit confirmation "
            "that the local entitlement is zero-cost; paid Data Lab access is "
            "not authorized by this research workflow"
        )
    if personal_research_rights_confirmed is not True:
        raise RuntimeError(
            "Phase 11 bounded JV-Link acquisition requires explicit confirmation "
            "of personal research rights before reading provider data"
        )

    if progress_callback is not None:
        progress_callback(
            "phase11_bounded_jvopen "
            f"range={plan.jvopen_range} option={plan.option} "
            "record_types=RA,SE holdout=2025-2026_untouched"
        )

    return exporter(
        output_path=output_path,
        summary_path=summary_path,
        from_time=plan.jvopen_range,
        option=plan.option,
        record_types=set(PHASE11_RECORD_TYPES),
        progress_callback=progress_callback,
    )
