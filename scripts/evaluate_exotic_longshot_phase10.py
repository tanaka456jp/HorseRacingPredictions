from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_longshot_phase10 import (
    evaluate_longshot_rolling_residual_phase10,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate research-only rolling longshot residual overlay "
            "on reused 2023/2024 development periods. "
            "2025-2026 remains untouched."
        )
    )
    parser.add_argument(
        "--history",
        default="data/jravan/full/current_history.csv",
    )
    parser.add_argument(
        "--output",
        default="artifacts/exotic_longshot_phase10/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    result = evaluate_longshot_rolling_residual_phase10(
        history,
    )

    output = Path(args.output)
    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({
        "status": result["status"],
        "oof_training": result["oof_training"],
        "annual_training": result["annual_training"],
        "evaluation_2023": result["evaluation_2023"],
        "evaluation_2024": result["evaluation_2024"],
        "development_longshot_rolling_residual_gate_passed": (
            result["development_longshot_rolling_residual_gate_passed"]
        ),
        "research_protocol": result["research_protocol"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
