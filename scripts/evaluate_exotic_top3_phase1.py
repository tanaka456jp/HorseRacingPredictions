from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_top3_research import (
    evaluate_exotic_top3_development,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate research-only Top-3 runner-vs-field interaction "
            "features on reused 2023/2024 development periods. "
            "2025-2026 remains untouched."
        )
    )
    parser.add_argument(
        "--history",
        default="data/jravan/full/current_history.csv",
    )
    parser.add_argument(
        "--output",
        default="artifacts/exotic_top3_phase1/summary.json",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=300,
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    result = evaluate_exotic_top3_development(
        history,
        iterations=args.iterations,
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
        "training": result["training"],
        "feature_design": result["feature_design"],
        "evaluation_2023": {
            "binary_log_loss_delta": (
                result["evaluation_2023"][
                    "binary_log_loss_delta"
                ]
            ),
            "brier_delta": (
                result["evaluation_2023"]["brier_delta"]
            ),
            "longshot_log_loss_delta": (
                result["evaluation_2023"]["longshot_proxy"][
                    "binary_log_loss_delta"
                ]
            ),
            "longshot_brier_delta": (
                result["evaluation_2023"]["longshot_proxy"][
                    "brier_delta"
                ]
            ),
        },
        "evaluation_2024": {
            "binary_log_loss_delta": (
                result["evaluation_2024"][
                    "binary_log_loss_delta"
                ]
            ),
            "brier_delta": (
                result["evaluation_2024"]["brier_delta"]
            ),
            "longshot_log_loss_delta": (
                result["evaluation_2024"]["longshot_proxy"][
                    "binary_log_loss_delta"
                ]
            ),
            "longshot_brier_delta": (
                result["evaluation_2024"]["longshot_proxy"][
                    "brier_delta"
                ]
            ),
        },
        "combination_phase3": {
            "evaluation_2023": (
                result["evaluation_2023"]["combination_phase3"]
            ),
            "evaluation_2024": (
                result["evaluation_2024"]["combination_phase3"]
            ),
            "development_combination_gate_passed": (
                result["development_combination_gate_passed"]
            ),
        },
        "development_gate_passed": (
            result["development_gate_passed"]
        ),
        "development_safety_gate_passed": (
            result["development_safety_gate_passed"]
        ),
        "research_protocol": result["research_protocol"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
