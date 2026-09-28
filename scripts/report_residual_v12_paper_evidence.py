import argparse
import json
from pathlib import Path

from horse_racing_predictions.residual_paper_evidence import (
    build_residual_v12_paper_evidence_report,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Write a sanitized evidence-sufficiency report for the "
            "prospective Residual v12 Paper v1 policy."
        )
    )
    parser.add_argument(
        "--ledger",
        default="data/paper/paper_trading.sqlite3",
    )
    parser.add_argument(
        "--output",
        default="artifacts/residual_v12_paper_evidence/summary.json",
    )
    args = parser.parse_args()

    report = build_residual_v12_paper_evidence_report(args.ledger)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
