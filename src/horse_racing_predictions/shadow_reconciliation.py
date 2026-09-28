from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from .residual_shadow_ledger import ResidualShadowLedger
from .residual_v12_shadow import capture_shadow_results_0b12


ResultFetcher = Callable[
    [pd.DataFrame],
    tuple[pd.DataFrame, int],
]


def reconcile_pending_shadow_results(
    ledger: ResidualShadowLedger,
    *,
    result_fetcher: ResultFetcher = capture_shadow_results_0b12,
) -> dict:
    pending_before = ledger.pending_race_ids()

    if pending_before:
        results, fetch_errors = result_fetcher(
            pd.DataFrame({"race_id": pending_before})
        )
    else:
        results = pd.DataFrame()
        fetch_errors = 0

    new_result_rows = ledger.record_results(results)
    pending_after = ledger.pending_race_ids()
    reconciled_races = len(
        set(pending_before) - set(pending_after)
    )
    cumulative = ledger.cumulative_summary()

    if not pending_before:
        status = "no_pending_results"
    elif not pending_after:
        status = "reconciled_all"
    elif reconciled_races:
        status = "partially_reconciled"
    else:
        status = "pending_results"

    return {
        "status": status,
        "result_fetch_errors": int(fetch_errors),
        "new_result_rows": int(new_result_rows),
        "pending_races_before": int(len(pending_before)),
        "pending_races_after": int(len(pending_after)),
        "reconciled_races": int(reconciled_races),
        "cumulative": cumulative,
    }
