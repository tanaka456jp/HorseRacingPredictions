from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from horse_racing_predictions.phase11_jravan_bounded import (
    PHASE11_MIN_START,
    PHASE11_SAFE_SETUP_END,
    build_phase11_bounded_plan,
    export_phase11_bounded_history,
    write_phase11_bounded_plan,
)


DEFAULT_RANGE = f"{PHASE11_MIN_START}-{PHASE11_SAFE_SETUP_END}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Plan or explicitly execute a provider-bounded pre-2025 JV-Link "
            "RA/SE acquisition for Phase 11. Default is plan-only."
        )
    )
    parser.add_argument(
        "--range",
        dest="jvopen_range",
        default=DEFAULT_RANGE,
        help=(
            "JVOpen START-END range. Phase 11 rejects any range that can "
            "cross into the protected 2025-2026 final holdout."
        ),
    )
    parser.add_argument(
        "--plan-output",
        default="artifacts/phase11_jravan_bounded_plan.json",
    )
    parser.add_argument(
        "--output",
        default="data/jravan/phase11_bounded/race_raw.jsonl",
    )
    parser.add_argument(
        "--summary",
        default="artifacts/phase11_jravan_bounded_summary.json",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually call JV-Link. Without this flag the command is metadata-"
            "only and never opens provider data."
        ),
    )
    parser.add_argument(
        "--zero-cost-entitlement-confirmed",
        action="store_true",
        help=(
            "Explicitly attest that the currently active local JV-Link "
            "entitlement is zero-cost. Does not authorize paid registration."
        ),
    )
    parser.add_argument(
        "--personal-research-rights-confirmed",
        action="store_true",
        help=(
            "Explicitly attest that the official terms have been reviewed for "
            "this local personal-research use."
        ),
    )
    return parser


def run(args: argparse.Namespace) -> dict:
    plan = build_phase11_bounded_plan(args.jvopen_range)
    plan_path = write_phase11_bounded_plan(
        plan,
        args.plan_output,
    )

    result = {
        "status": "plan_only",
        "plan": asdict(plan),
        "plan_output": str(Path(plan_path)),
        "provider_opened": False,
        "records_written": 0,
    }

    if not args.execute:
        return result

    if args.zero_cost_entitlement_confirmed is not True:
        raise RuntimeError(
            "--execute requires --zero-cost-entitlement-confirmed"
        )
    if args.personal_research_rights_confirmed is not True:
        raise RuntimeError(
            "--execute requires --personal-research-rights-confirmed"
        )

    summary = export_phase11_bounded_history(
        jvopen_range=args.jvopen_range,
        output_path=args.output,
        summary_path=args.summary,
        zero_cost_entitlement_confirmed=True,
        personal_research_rights_confirmed=True,
    )
    return {
        "status": "bounded_export_complete",
        "plan": asdict(plan),
        "plan_output": str(Path(plan_path)),
        "provider_opened": True,
        "records_written": int(summary.records_written),
        "output_sha256": summary.output_sha256,
        "raw_redistribution_allowed": False,
        "summary_path": str(Path(args.summary)),
    }


def main() -> None:
    args = build_parser().parse_args()
    print(
        json.dumps(
            run(args),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
