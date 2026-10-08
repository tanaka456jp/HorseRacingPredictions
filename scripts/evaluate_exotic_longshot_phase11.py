"""Evaluate race-centered longshot residual research on 2023/2024."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_longshot_phase11 import (
    evaluate_longshot_race_centered_phase11,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 11 development evaluation")
    parser.add_argument("--history", default="data/jravan/full/current_history.csv")
    parser.add_argument("--output", default="artifacts/exotic_longshot_phase11/summary.json")
    args = parser.parse_args()
    result = evaluate_longshot_race_centered_phase11(
        read_csv_flexible(args.history, low_memory=False)
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
