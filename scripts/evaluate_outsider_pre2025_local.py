"""Local-only pre-2025 independent outsider study; outputs aggregate metrics.

No JRA-VAN API, web scraping, protected holdout, model save, note session,
real bet, raw starter data export, or automatic publication. The caller must
supply an independently approved historical CSV; this CLI does NOT grant
data licensing or prove model/market-independent selection provenance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.odds_free_training import (
    prepare_strict_odds_free_training_sample,
)
from horse_racing_predictions.odds_free_outsider_eval import (
    evaluate_independent_outsider_chronologically,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history-csv", type=Path, required=True)
    parser.add_argument("--train-start", required=True)
    parser.add_argument("--train-end", required=True)
    parser.add_argument("--fit-through", required=True)
    parser.add_argument("--validation-from", required=True)
    parser.add_argument("--validation-through", required=True)
    args = parser.parse_args()
    path = args.history_csv
    # Only an explicitly nominated local file may be inspected. Never scan
    # private folders or cross into redirected symbolic-link targets.
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size <= 400_000_000
            or path.suffix.lower() != ".csv"):
        print(json.dumps({
            "status": "BLOCKED", "reason": "LOCAL_APPROVED_CSV_UNAVAILABLE",
            "publicationAuthorized": False,
        }, ensure_ascii=False))
        return 2
    try:
        raw = read_csv_flexible(path)
        sample = prepare_strict_odds_free_training_sample(
            raw, train_start=args.train_start, train_end=args.train_end,
        )
        result = evaluate_independent_outsider_chronologically(
            sample, fit_through=args.fit_through,
            validation_from=args.validation_from,
            validation_through=args.validation_through,
        )
    except (ValueError, TypeError, KeyError, OSError, UnicodeError):
        # Do not leak protected/local path, source data or horse identities.
        print(json.dumps({
            "status": "BLOCKED", "reason": "RESEARCH_INPUT_OR_SPLIT_REJECTED",
            "publicationAuthorized": False,
        }, ensure_ascii=False))
        return 2
    print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
