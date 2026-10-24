from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from horse_racing_predictions.exotic_conditional_partner_phase13 import (
    evaluate_conditional_partner_phase13,
)
from horse_racing_predictions.jravan_archive_paths import (
    default_archive_root,
)
from horse_racing_predictions.jravan_archive_provenance import (
    validate_local_pre2025_archive,
)
from horse_racing_predictions.jravan_parser import (
    parse_raw_jsonl,
)
from horse_racing_predictions.one_shot_evaluation_receipt import (
    claim_one_shot,
    finalize_one_shot,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the preregistered one-shot Phase 13 conditional-partner "
            "evaluation using only the local provider-bounded pre-2025 "
            "JRA-VAN RACE archive."
        )
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "artifacts/exotic_conditional_partner_phase13/summary.json"
        ),
    )
    args = parser.parse_args()

    root = args.archive_root or default_archive_root()
    receipt_path = root / "phase13_evaluation_receipt.json"

    if receipt_path.exists():
        raise RuntimeError(
            "Phase 13 real-data evaluation already has a local receipt; "
            "the preregistered one-shot evaluation must not be rerun."
        )
    provenance = validate_local_pre2025_archive(
        root,
        required_dataspecs=("RACE",),
    )
    race_part = provenance.parts[0]
    race_raw = race_part.path
    race_sha256 = race_part.sha256

    # Atomic one-shot before raw archive parsing; failures cannot be retried.
    one_shot_claim = claim_one_shot(
        receipt_path, phase=13, race_archive_sha256=race_sha256,
    )
    history, parse_report = parse_raw_jsonl(
        race_raw,
        jra_only=True,
        completed_only=True,
    )
    if history.empty:
        raise RuntimeError(
            "local bounded RACE archive produced no completed JRA history"
        )

    result = evaluate_conditional_partner_phase13(
        history
    )
    result["input_provenance"] = {
        "race_archive": "private local pre2025/race_raw.jsonl",
        "race_archive_sha256": race_sha256,
        "parse_spec_version": parse_report.spec_version,
        "history_rows": int(parse_report.output_rows),
        "history_races": int(parse_report.output_races),
        "current_history_csv_used": False,
        "protected_holdout": "2025-2026 untouched",
        "archive_manifest": str(provenance.manifest_path),
        "archive_manifest_status": provenance.manifest_status,
        "archive_jvopen_range": provenance.jvopen_range,
        "race_manifest_records_written": race_part.records_written,
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    output_sha256 = _sha256(args.output)

    finalize_one_shot(
        receipt_path, claim=one_shot_claim,
        summary_sha256=output_sha256,
        passed=bool(result["development_conditional_partner_gate_passed"]),
    )

    print(json.dumps({
        "status": result["status"],
        "history_rows": int(parse_report.output_rows),
        "history_races": int(parse_report.output_races),
        "evaluation_2023": {
            "anchor_top3_hit_rate": (
                result["evaluation_2023"][
                    "nominated_anchor_top3_hit_rate"
                ]
            ),
            "exact_pair_delta": (
                result["evaluation_2023"][
                    "exact_partner_pair_hit_rate_delta"
                ]
            ),
            "recall_at_2_delta": (
                result["evaluation_2023"][
                    "partner_recall_at_2_delta"
                ]
            ),
        },
        "evaluation_2024": {
            "anchor_top3_hit_rate": (
                result["evaluation_2024"][
                    "nominated_anchor_top3_hit_rate"
                ]
            ),
            "exact_pair_delta": (
                result["evaluation_2024"][
                    "exact_partner_pair_hit_rate_delta"
                ]
            ),
            "recall_at_2_delta": (
                result["evaluation_2024"][
                    "partner_recall_at_2_delta"
                ]
            ),
        },
        "development_conditional_partner_gate_passed": (
            result[
                "development_conditional_partner_gate_passed"
            ]
        ),
        "one_shot_receipt": str(receipt_path),
        "rerun_allowed": False,
        "protected_holdout": "2025-2026 untouched",
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
