from __future__ import annotations

import argparse
import json
from pathlib import Path

from horse_racing_predictions.data_sources import read_csv_flexible
from horse_racing_predictions.exotic_trio_phase6 import (
    evaluate_direct_trio_phase6,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate research-only direct three-runner set ranker "
            "against the frozen Phase 5 exact-three baseline. "
            "2025-2026 remains untouched."
        )
    )
    parser.add_argument(
        "--history",
        default="data/jravan/full/current_history.csv",
    )
    parser.add_argument(
        "--output",
        default="artifacts/exotic_trio_phase6/summary.json",
    )
    args = parser.parse_args()

    history = read_csv_flexible(
        args.history,
        low_memory=False,
    )
    result = evaluate_direct_trio_phase6(
        history,
    )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
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
        "evaluation_2023": result["evaluation_2023"],
        "evaluation_2024": result["evaluation_2024"],
        "development_direct_trio_gate_passed": (
            result["development_direct_trio_gate_passed"]
        ),
        "research_protocol": result["research_protocol"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
