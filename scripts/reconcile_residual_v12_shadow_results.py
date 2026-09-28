import argparse
import json
from pathlib import Path

from horse_racing_predictions.market_residual_v12_holdout import (
    FIXED_GAMMA,
)
from horse_racing_predictions.residual_shadow_ledger import (
    ResidualShadowLedger,
)
from horse_racing_predictions.shadow_reconciliation import (
    reconcile_pending_shadow_results,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile results for races already stored in the frozen "
            "Residual v12 local shadow ledger without regenerating predictions."
        )
    )
    parser.add_argument(
        "--ledger",
        default="data/jravan/forward/residual_v12_shadow.sqlite3",
    )
    parser.add_argument(
        "--summary-output",
        default="artifacts/residual_v12_shadow/reconcile_summary.json",
    )
    args = parser.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.is_file() or ledger_path.stat().st_size == 0:
        raise FileNotFoundError(
            f"Residual v12 shadow ledger is missing: {ledger_path}"
        )

    ledger = ResidualShadowLedger(ledger_path)
    try:
        reconciliation = reconcile_pending_shadow_results(ledger)
    finally:
        ledger.close()

    payload = {
        **reconciliation,
        "fixed_gamma": float(FIXED_GAMMA),
        "predictions_regenerated": False,
        "holdout_reused": False,
        "paper_broker_unchanged": True,
        "horse_level_data_uploaded": False,
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
