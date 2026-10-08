"""Evaluate Phase 11 using an isolated, development-only history file.

Never use current_history.csv: it can include the final 2025-2026 holdout.
The approved input must be separately staged from a pre-2025 data source.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_longshot_phase11 import (
    evaluate_longshot_race_centered_phase11,
)

DEVELOPMENT_HISTORY_RELATIVE_PATH = Path(
    "data/jravan/development/history_through_2024.csv"
)


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
    component = root
    for part in DEVELOPMENT_HISTORY_RELATIVE_PATH.parts:
        component = component / part
        if component.is_symlink() or getattr(
            component, "is_junction", lambda: False
        )():
            raise ValueError(
                "Phase 11 refuses symlinks/junctions in the development "
                f"snapshot path: {component}"
            )
    if not approved.resolve().is_relative_to(root):
        raise ValueError("Phase 11 development snapshot escapes project root")
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
