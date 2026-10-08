"""Evaluate Phase 11 using an isolated, development-only history file.

Never use current_history.csv: it can include the final 2025-2026 holdout.
The approved input must be separately staged from a pre-2025 data source.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_longshot_phase11 import (
    evaluate_longshot_race_centered_phase11,
)

DEVELOPMENT_HISTORY_RELATIVE_PATH = Path(
    "data/research/development/free_history_through_2024.csv"
)
SOURCE_APPROVAL_RELATIVE_PATH = Path(
    "data/research/development/source_approval.json"
)



def _reject_path_aliases(root: Path, relative: Path) -> Path:
    """Reject filesystem aliases without opening historical race data."""
    component = root
    for part in relative.parts:
        component = component / part
        if component.is_symlink() or getattr(
            component, "is_junction", lambda: False
        )():
            raise ValueError(
                f"Phase 11 refuses symlinks/junctions: {component}"
            )
    if not component.resolve().is_relative_to(root):
        raise ValueError("Phase 11 path escapes project root")
    return component


def _require_approved_free_source(root: Path) -> None:
    """Require independent free-source attestation BEFORE opening the CSV.

    The manifest is a provenance assertion, not proof of the CSV contents.
    Do not create it automatically from the combined/full history file.
    """
    manifest = _reject_path_aliases(root, SOURCE_APPROVAL_RELATIVE_PATH)
    if not manifest.is_file():
        raise FileNotFoundError(
            "Phase 11 requires a manually verified independent free-source "
            f"approval manifest at {SOURCE_APPROVAL_RELATIVE_PATH}; "
            "no full-history fallback is permitted."
        )
    try:
        approval = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Phase 11 source approval manifest is invalid") from exc
    if not isinstance(approval, dict):
        raise ValueError("Phase 11 source approval manifest must be an object")
    required = {
        "schema_version": 1,
        "approved_for_phase11": True,
        "source_type": "independent_free_pre2025_export",
        "contains_final_holdout": False,
    }
    if any(type(approval.get(k)) is not type(v) or approval.get(k) != v
           for k, v in required.items()):
        raise ValueError("Phase 11 requires explicit approved free-source provenance")
    if not isinstance(approval.get("source_name"), str) or not approval[
        "source_name"
    ].strip():
        raise ValueError("Phase 11 source name is missing")
    try:
        cutoff = date.fromisoformat(approval["source_cutoff"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Phase 11 source cutoff is invalid") from exc
    if cutoff > date(2024, 12, 31):
        raise ValueError("Phase 11 source approval includes final holdout dates")


def approved_development_history_path(
    candidate: str | Path, *, project_root: Path | None = None
) -> Path:
    """Reject any path other than the isolated development snapshot BEFORE I/O."""
    root = (
        Path(project_root)
        if project_root is not None
        else Path(__file__).resolve().parents[1]
    )
    root = root.resolve(strict=True)
    approved = root / DEVELOPMENT_HISTORY_RELATIVE_PATH
    requested = Path(candidate)
    if not requested.is_absolute():
        requested = root / requested
    # Compare the lexical path before following any filesystem aliases.
    # In particular, an attacker must not substitute a symlinked snapshot.
    if requested != approved:
        raise ValueError(
            "Phase 11 refuses general/full history files. Stage a separately "
            "sourced pre-2025 development snapshot at "
            f"{DEVELOPMENT_HISTORY_RELATIVE_PATH}; do not extract it from the "
            "2025-2026 final holdout."
        )
    _reject_path_aliases(root, DEVELOPMENT_HISTORY_RELATIVE_PATH)
    _require_approved_free_source(root)
    if not approved.is_file():
        raise FileNotFoundError(
            f"Missing isolated development-only snapshot: {approved}. "
            "Do not read current_history.csv as a fallback."
        )
    return approved


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 development evaluation")
    parser.add_argument(
        "--history", default=str(DEVELOPMENT_HISTORY_RELATIVE_PATH)
    )
    parser.add_argument(
        "--output", default="artifacts/exotic_longshot_phase11/summary.json"
    )
    args = parser.parse_args()
    approved_path = approved_development_history_path(args.history)
    result = evaluate_longshot_race_centered_phase11(
        read_csv_flexible(str(approved_path), low_memory=False)
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
