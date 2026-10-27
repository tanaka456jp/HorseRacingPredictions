"""Local-only strict non-market CatBoost win + outsider research trainer.

Needs operator-reviewed PRE-2025-only historical CSV and a fresh absolute
artifact directory. Never fetches data, connects JV-Link, touches note,
opens the protected final holdout as a separate dataset, or uploads models.
Do not pass a mixed/holdout-containing CSV to this offline research command.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

import pandas as pd

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.pre2025_training_csv_audit import (
    audit_pre2025_training_csv,
)
from horse_racing_predictions.pre2025_multiyear_csv_audit import (
    audit_multiyear_pre2025_csvs,
)
from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from horse_racing_predictions.friday_predraw_features import (
    select_friday_predraw_research_features,
)
from horse_racing_predictions.strict_dual_catboost_candidate import (
    fit_strict_dual_catboost_candidate, save_dual_candidate_for_research,
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--approved-pre2025-csv", type=Path, nargs="+", required=True,
                   help="explicit local CSVs only, no directory discovery")
    p.add_argument("--source-ref", required=True,
                   help="nonsecret operator-reviewed source evidence ID")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="brand-new absolute local candidate dir; never main")
    p.add_argument("--train-start", required=True)
    p.add_argument("--train-end", required=True)
    p.add_argument("--fit-through", required=True)
    p.add_argument("--validation-from", required=True)
    p.add_argument("--validation-through", required=True)
    p.add_argument("--iterations", type=int, default=100)
    p.add_argument("--friday-predraw", action="store_true",
                   help="drop Saturday draw/day-of-race features before fitting")
    a = p.parse_args()
    try:
        csvs = a.approved_pre2025_csv
        if (not 1 <= len(csvs) <= 12 or len(set(csvs)) != len(csvs)
                or any(not source.is_absolute() or source.is_symlink()
                       or not source.is_file() or source.suffix.lower() != ".csv"
                       or not 0 < source.stat().st_size <= 400_000_000
                       for source in csvs)):
            raise ValueError("explicit approved local pre2025 CSVs required")
        if not a.output_dir.is_absolute() or a.output_dir.exists():
            raise ValueError("new absolute output candidate directory required")
        # Audit every full input BEFORE pandas materializes training rows.
        # This audit is technical only: it cannot grant research rights.
        if len(csvs) == 1:
            audit_pre2025_training_csv(csvs[0])
        else:
            audit_multiyear_pre2025_csvs(csvs)
        frames = []
        expected_columns = None
        for source in csvs:
            frame = read_csv_flexible(source)
            cols = tuple(frame.columns)
            if (frame.columns.duplicated().any()
                    or (expected_columns is not None
                        and cols != expected_columns)):
                raise ValueError("annual training CSV schema mismatch")
            expected_columns = cols
            frames.append(frame)
        sample = prepare_strict_odds_free_training_sample(
            pd.concat(frames, ignore_index=True),
            train_start=a.train_start, train_end=a.train_end,
        )
        if a.friday_predraw:
            sample = select_friday_predraw_research_features(sample)
        candidate = fit_strict_dual_catboost_candidate(
            sample, fit_through=a.fit_through,
            validation_from=a.validation_from,
            validation_through=a.validation_through,
            iterations=a.iterations,
        )
        saved = save_dual_candidate_for_research(
            candidate, destination=a.output_dir, source_ref=a.source_ref,
        )
        outcome = {
            "status": saved["status"],
            "artifactSha256": saved["artifactSha256"],
            "metrics": asdict(candidate.metrics),
            "publicationAuthorized": False,
            "positiveExpectedValueDemonstrated": False,
        }
        print(json.dumps(outcome, ensure_ascii=False, sort_keys=True,
                         allow_nan=False))
        return 0
    except (OSError, KeyError, TypeError, ValueError, RuntimeError,
            ImportError, UnicodeError):
        # No user paths, filenames, horse IDs or licensed data leave the PC.
        print(json.dumps({
            "status": "BLOCKED",
            "blockers": ["PRE2025_SOURCE_MODEL_TRAINING_OR_FREEZE_NOT_VERIFIED"],
            "publicationAuthorized": False,
            "positiveExpectedValueDemonstrated": False,
        }, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
