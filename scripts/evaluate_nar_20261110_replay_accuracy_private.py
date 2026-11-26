"""Descriptive postevent comparison on the previously evaluated Nov 10 card.

No new downloads, training, original snapshot edits, or protected OOS access.
The CatBoost picks are calculated AFTER the event, never prospective proof.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
from zipfile import ZipFile

from capture_nar_official_daily_odds_preoff_once import _load_original_frozen_forecast
from capture_nar_official_daily_preoff_once import _rows
from freeze_nar_partial_catboost_daily_private import freeze_partial_from_official_source
from horse_racing_predictions.nar_private_dual_model_loader import load_nar_private_dual_candidate
from reconcile_nar_20261110_forward_official_results import (
    _TARGET, _MAX_BYTES, _rid, _FINAL_FINISH, _MARKER_GROUPS,
    _payout_table, verify_real_forward_final_results,
)

_SCHEMA = "NAR.PC2.HistoricalDescriptiveModelComparison.v1"


def metrics(picks, ranks, statuses, pays):
    """Full-card accuracy; no-offer WIN slots retained in accuracy denominator."""
    if not picks or set(picks) != set(ranks) or set(picks) != set(statuses) or set(picks) != set(pays):
        raise ValueError("REPLAY_COHORT_MISMATCH")
    hits = top3 = outside = stake = returns = no_offer = refunded = 0
    for rid, (three, outsider) in picks.items():
        row = ranks[rid]
        status = statuses[rid]
        wins = pays[rid][0]
        if (set(row) != set(status) or len(three) != 3 or len(set(three)) != 3
                or outsider in three or not set((*three, outsider)).issubset(row)
                or set(wins) != {h for h, rank in row.items() if rank == 1}
                or not wins):
            raise ValueError("REPLAY_RANK_OR_PAYOUT_MISMATCH")
        selected = three[0]
        hits += int(row[selected] == 1)
        top3 += sum(0 < row[h] <= 3 for h in three)
        outside += int(0 < row[outsider] <= 3)
        if status[selected] == "SCRATCH_NOT_OFFERED":
            no_offer += 1
        elif status[selected] == "EXCLUDED_REFUND":
            stake += 100
            returns += 100
            refunded += 1
        elif status[selected] in {"FINISHED", "DNF_NO_REFUND"}:
            stake += 100
            returns += wins.get(selected, 0)
        else:
            raise ValueError("REPLAY_SELECTED_STATUS_UNKNOWN")
    n = len(picks)
    if not stake:
        raise ValueError("REPLAY_NO_PAPER_STAKE")
    return {
        "races": n, "top1_hits": hits, "top1_hit_rate": hits/n,
        "top3_hits": top3, "top3_precision": top3/(3*n),
        "outsider_top3_hits": outside, "outsider_top3_rate": outside/n,
        "paper_win_stake_yen": stake, "paper_win_return_yen": returns,
        "paper_win_gross_return_rate": returns/stake,
        "paper_win_net_roi": (returns-stake)/stake,
        "no_offer_win_slots": no_offer, "refunded_win_slots": refunded,
    }


def _read_final(folder, baseline):
    files = list(folder.glob("20261110_*_official_postevent_race.zip"))
    if len(files) != 1:
        raise ValueError("REPLAY_FINAL_SOURCE_NOT_UNIQUE")
    path = files[0]
    meta = path.with_name(path.name.replace("_official_postevent_race.zip", "_official_postevent_audit_PRIVATE.json"))
    for file, maximum in ((path, _MAX_BYTES), (meta, 500_000)):
        if not file.is_file() or file.is_symlink() or not 32 < file.stat().st_size <= maximum:
            raise ValueError("REPLAY_FINAL_SOURCE_INVALID")
    doc = json.loads(meta.read_text(encoding="utf-8"))
    if (doc.get("schema") != "NAR.PC2.RealProspectiveDaySettlementPrivate.v1"
            or doc.get("frozen_commitment_digest") != baseline["commitment_digest"]
            or doc.get("raw_lawful_source_never_uploaded") is not True):
        raise ValueError("REPLAY_FINAL_SOURCE_PROVENANCE_INVALID")
    return path.read_bytes(), doc


def evaluate(root: Path):
    if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
            or not root.is_absolute() or not root.is_dir() or root.is_symlink()):
        raise ValueError("REPLAY_PC2_CONTEXT_INVALID")
    folder = root / "nar-prospective-captures"
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("REPLAY_CAPTURE_FOLDER_INVALID")
    baseline, original = _load_original_frozen_forecast(folder, _TARGET)
    model = load_nar_private_dual_candidate(root / "nar-forward-models/2017-2021-fit-2022-tune-v1")
    replay, counts = freeze_partial_from_official_source(
        original, day=_TARGET, observed_utc=datetime.fromisoformat(baseline["host_observed_utc"]),
        generated_utc=datetime.fromisoformat(baseline["host_generated_utc"]), loaded=model)
    if len(replay.races) != 59 or counts["runners"] != 641:
        raise ValueError("REPLAY_WRONG_COHORT")
    # Only after fixed replay picks have been computed do we open the
    # previously reviewed final ZIP. Never modify the original baseline.
    final, meta = _read_final(folder, baseline)
    review = verify_real_forward_final_results(
        baseline, original, final, result_source_name=meta["official_source_name"],
        observed_utc=datetime.fromisoformat(meta["captured_utc"]))
    if review.unresolved_races or review.fully_interpretable_races != 59:
        raise ValueError("REPLAY_ORIGINAL_FINAL_UNRESOLVED")
    previous = meta["audit"]
    for k in ("frozen_flat_races", "frozen_horses", "official_result_races",
              "official_result_horses", "official_payback_races"):
        if previous.get(k) != getattr(review, k):
            raise ValueError("REPLAY_OLD_AUDIT_MISMATCH")
    basic = {r["race_id"]: (tuple(r["top3"]), r["outsider"])
             for r in baseline["complete_private_forecasts"]}
    fitted = {r.race_id: (r.top3, r.outsider) for r in replay.races}
    if len(basic) != 59 or set(basic) != set(fitted):
        raise ValueError("REPLAY_PICK_COHORT_MISMATCH")
    with ZipFile(BytesIO(final)) as z:
        horses = _rows(z.read("20261110_horselist.csv"), {
            "競馬場", "競走年月日", "レース番号", "馬番", "着順", "着差"})
        pay = _rows(z.read("20261110_payback.csv"), {
            "競馬場", "競走年月日", "レース番号", "単勝組番", "単勝払戻金（円）",
            "複勝組番1", "複勝払戻金1（円）", "複勝組番2", "複勝払戻金2（円）",
            "複勝組番3", "複勝払戻金3（円）"})
    ranks, statuses = {}, {}
    for row in horses:
        if row["競馬場"].strip().startswith("帯広"):
            continue
        rid = _rid(row, day=_TARGET)
        h = str(int(row["馬番"].strip()))
        if h in ranks.setdefault(rid, {}):
            raise ValueError("REPLAY_DUPLICATE_HORSE")
        value = row["着順"].strip()
        if _FINAL_FINISH.fullmatch(value):
            ranks[rid][h] = int(value)
            statuses.setdefault(rid, {})[h] = "FINISHED"
        else:
            marker = row["着差"].strip()
            category = _MARKER_GROUPS.get(marker if marker in _MARKER_GROUPS else value)
            if category not in {"SCRATCH_NOT_OFFERED", "EXCLUDED_REFUND", "DNF_NO_REFUND"}:
                raise ValueError("REPLAY_UNKNOWN_STATUS")
            ranks[rid][h] = 0
            statuses.setdefault(rid, {})[h] = category
    for race in replay.races:
        if set(race.roster) != set(ranks.get(race.race_id, {})):
            raise ValueError("REPLAY_FINAL_ROSTER_MISMATCH")
    if sum(map(len, ranks.values())) != 641:
        raise ValueError("REPLAY_FINAL_RUNNER_COUNT_MISMATCH")
    payouts = _payout_table(pay, day=_TARGET, frozen_ids=set(basic))
    return {
        "schema": _SCHEMA, "status": "COMPLETE_HISTORICAL_DESCRIPTIVE_REPLAY_NOT_FORWARD",
        "race_day": _TARGET.isoformat(), "races": 59, "runners": 641,
        "career_baseline": metrics(basic, ranks, statuses, payouts),
        "catboost_partial_3_of_5": metrics(fitted, ranks, statuses, payouts),
        "catboost_selection_before_event": False,
        "prospective_hit_rate_measured": False, "prospective_roi_measured": False,
        "positive_ev_proven": False, "actual_bets": 0,
        "private_source_uploaded": False, "original_files_modified": False,
        "protected_holdout_opened": False,
        "final_zip_original_hash_independently_verified": False,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--private-root", type=Path, required=True)
    args = p.parse_args()
    try:
        result = evaluate(args.private_root)
    except Exception:
        print(json.dumps({"schema": _SCHEMA, "status": "HOLD_REAL_REPLAY_COMPARISON_UNVERIFIED",
                          "positive_ev_proven": False}))
        return 2
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
