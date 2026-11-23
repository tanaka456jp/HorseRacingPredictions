"""PC2-only *exploratory* 2017-2022 ranking screen on genuine NAR ZIPs.

2017-2021 fit; 2022 tune. No historical betting odds prior to 2026-03,
no genuinely frozen historical preoff roster, no economic EV estimator.
851+ unresolved race outcomes remain in the source denominator.
Strict production training approval remains HOLD.

Default mode never exports models. An explicit private PC2 output directory\nmay opt in to a hash-verified research artifact; no source rows uploaded.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import os
import json
import re
from pathlib import Path

from horse_racing_predictions.nar_local_monthly_intake import _read_nar_local_csv_texts
from horse_racing_predictions.nar_official_exception_audit import audit_nar_official_exceptions
from horse_racing_predictions.nar_economic_settlement_adapter import nar_canonical_race_id
from horse_racing_predictions.nar_official_zip_probe import UnsafeNarSource
from horse_racing_predictions.nar_private_manifest_inventory import inventory_private_nar_training_directory
from horse_racing_predictions.nar_published_result_normalizer import _parse
from horse_racing_predictions.nar_status_aware_training_labels import derive_nar_status_aware_outcome_labels
from horse_racing_predictions.nar_status_aware_prior_day import reconstruct_nar_status_aware_prior_day


def save_nar_exploratory_models_private(
    winner, outsider, metrics, destination: Path,
) -> dict:
    """Optional research-only artifact compatible with the verified loader.

    Only a fresh local directory; no historical licensed rows, filenames,
    or horse identities appear in the saved model manifest or public logs.
    """
    from horse_racing_predictions.modeling import CatBoostProbabilityModel
    from horse_racing_predictions.nar_exploratory_rank_screen import (
        _FEATURES, NarExploratoryRankingMetrics,
    )
    if (not isinstance(destination, Path) or not destination.is_absolute()
            or destination.exists() or destination.is_symlink()
            or not destination.parent.is_dir() or destination.parent.is_symlink()
            or not isinstance(metrics, NarExploratoryRankingMetrics)
            or not metrics.independently_fitted_models
            or metrics.positive_expected_value_demonstrated
            or not isinstance(winner, CatBoostProbabilityModel)
            or not isinstance(outsider, CatBoostProbabilityModel)
            or winner is outsider or winner.model is None
            or outsider.model is None or winner.model is outsider.model
            or tuple(winner.feature_columns) != _FEATURES
            or tuple(outsider.feature_columns) != _FEATURES):
        raise UnsafeNarSource("NAR_EXPLORATORY_MODEL_EXPORT_GATE_INVALID")
    destination.mkdir()
    digests = {}
    for filename, model in (("win.cbm", winner), ("outsider.cbm", outsider)):
        target = destination / filename
        if target.exists() or target.is_symlink():
            raise UnsafeNarSource("NAR_EXPLORATORY_MODEL_BINARY_ALREADY_EXISTS")
        model.model.save_model(str(target))
        if not target.is_file() or target.is_symlink():
            raise UnsafeNarSource("NAR_EXPLORATORY_MODEL_BINARY_MISSING")
        digests[filename] = sha256(target.read_bytes()).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "artifactKind": "dual-catboost-oddsfree-research-candidate",
        "status": "RESEARCH_NOT_APPROVED_FOR_PUBLICATION",
        "jurisdiction": "NAR",
        "sourceRef": "nar-personal-2017-2022-72months-reviewed-local",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "featureColumns": list(_FEATURES),
        "trainStart": "2017-01-01",
        "trainEnd": "2021-12-31",
        "artifactSha256": digests,
        "researchMetrics": {
            "fitThrough": "2021-12-31",
            "winModelTarget": "is_winner",
            "outsiderModelTarget": "finish_position_le_3_train_only",
            "trainingRaces": metrics.fit_races_2017_2021,
            "validationRaces": metrics.tune_races_2022,
            "validationTop1HitRate": metrics.winner_top1_hit_rate_2022,
            "publicationAuthorized": False,
            "positiveExpectedValueDemonstrated": False,
        },
        "publicationAuthorized": False,
        "retrainingOnProtectedHoldoutAllowed": False,
        "sourceRightsIndependentlyVerified": False,
        "independentOutsiderModelVerified": False,
        "modelRuntimeProvenanceVerified": False,
        "sourceRowsOrRaceIdentitiesExported": False,
    }
    target = destination / "candidate_manifest.json"
    fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, sort_keys=True,
                  indent=2, allow_nan=False)
        out.flush()
        os.fsync(out.fileno())
    return {
        "status": "PRIVATE_NAR_RESEARCH_CANDIDATE_FROZEN_NOT_APPROVED",
        "artifactSha256": digests,
        "publicationAuthorized": False,
        "sourceUploaded": False,
    }


def screen_private_72_month_exploratory(
    folder: Path, *, permission: bool, iterations: int = 40,
    candidate_output_dir: Path | None = None,
) -> dict:
    if permission is not True:
        raise UnsafeNarSource("NAR_EXPLORATORY_PRIVATE_PERMISSION_REQUIRED")
    # Existing research workflow invokes this with None (no export).
    # New opt-in requires the physical PC2 and a fresh D: private directory.
    if candidate_output_dir is not None:
        private_root = Path(
            r"D:\Development\HorseRacingPredictions-PrivateReview"
        )
        if (os.environ.get("COMPUTERNAME") != "DESKTOP-MVV1FD4"
                or not candidate_output_dir.is_absolute()
                or candidate_output_dir.exists() or candidate_output_dir.is_symlink()
                or not private_root.is_dir() or private_root.is_symlink()
                or not candidate_output_dir.parent.is_dir()
                or candidate_output_dir.parent.is_symlink()
                or not candidate_output_dir.parent.resolve().is_relative_to(
                    private_root.resolve()
                )):
            raise UnsafeNarSource("NAR_EXPLORATORY_MODEL_PRIVATE_PATH_INVALID")
    inventory = inventory_private_nar_training_directory(
        folder, personal_private_permission_confirmed=True,
    )
    if (inventory.missing_months or len(inventory.absolute_source_paths) != 72):
        raise UnsafeNarSource("NAR_EXPLORATORY_72_MONTHS_REQUIRED")
    # Post-race payout values are never model features; keep privately in memory.
    official_2022_win_returns: dict[str, dict[int, int]] = {}
    official_2022_place_returns: dict[str, dict[int, int]] = {}
    annual: Counter[int] = Counter()
    totals: Counter[str] = Counter()

    def monthly():
        for p in inventory.absolute_source_paths:
            expected = p.name[:6]
            month, texts = _read_nar_local_csv_texts(
                p, personal_private_permission_confirmed=True,
            )
            if month != expected:
                raise UnsafeNarSource("NAR_EXPLORATORY_MONTH_MISMATCH")
            assessment = audit_nar_official_exceptions(
                texts, month=month,
            )
            a = assessment.audit
            annual[int(month[:4])] += a.in_scope_flat_races
            totals["months"] += 1
            totals["source"] += a.source_races
            totals["banei"] += a.predeclared_banei_races
            totals["flat"] += a.in_scope_flat_races
            totals["validated"] += a.status_validated_flat_races
            totals["unresolved"] += a.unresolved_flat_races
            if month.startswith("2022"):
                for race in assessment.validated_races:
                    rid = nar_canonical_race_id(race.race_key)
                    if rid in official_2022_win_returns:
                        raise UnsafeNarSource("NAR_EXPLORATORY_DUPLICATE_PAYOUT_RACE")
                    statuses = dict(race.status_by_number)
                    payouts = dict(race.win_yen_by_number)
                    place_payouts = dict(race.place_yen_by_number)
                    amounts = {}
                    places = {}
                    for number, status in statuses.items():
                        if status in {"FINISHED", "DNF_NO_REFUND"}:
                            value = payouts[number]
                            if type(value) is not int or value < 0:
                                raise UnsafeNarSource("NAR_EXPLORATORY_PAYOUT_INVALID")
                            amounts[number] = value
                            place_value = place_payouts[number]
                            if type(place_value) is not int or place_value < 0:
                                raise UnsafeNarSource("NAR_EXPLORATORY_PLACE_PAYOUT_INVALID")
                            places[number] = place_value
                    official_2022_win_returns[rid] = amounts
                    official_2022_place_returns[rid] = places
            labels = derive_nar_status_aware_outcome_labels(assessment)
            required = {(row.race_key, row.horse_number)
                        for row in labels.labels}
            identities = {}
            for key, row in _parse(texts["horselist"], "horselist", month):
                raw_number = row[5].strip()
                if not raw_number.isascii() or not raw_number.isdecimal():
                    continue
                idx = (key, int(raw_number))
                if idx in required:
                    if idx in identities:
                        raise UnsafeNarSource(
                            "NAR_EXPLORATORY_DUPLICATE_PRIVATE_HORSE"
                        )
                    identities[idx] = row[6], row[10]
            if set(identities) != required:
                raise UnsafeNarSource("NAR_EXPLORATORY_IDENTITY_COVERAGE_HOLD")
            yield month, labels, identities

    # This opt-in is isolated from production: its audit still says
    # usable_for_training=False and its sample is never saved/uploaded.
    form = reconstruct_nar_status_aware_prior_day(
        monthly(), allow_incomplete_diagnostic=True,
        allow_explicit_exploratory_sample=True,
    )
    audit = form.audit
    if (totals["months"] != 72 or totals["source"] != totals["flat"] + totals["banei"]
            or totals["flat"] != totals["validated"] + totals["unresolved"]
            or totals["flat"] != audit.source_flat_races
            or totals["validated"] != audit.validated_flat_races
            or totals["unresolved"] != audit.unresolved_flat_races
            or not audit.unresolved_flat_races
            or audit.usable_for_training
            or audit.independent_oos_opened):
        raise UnsafeNarSource("NAR_EXPLORATORY_FULL_DENOMINATOR_CONFLICT")

    # Heavy ML dependency is loaded only after all 72 months are
    # chronologically reconciled. Never open sealed or future periods.
    from horse_racing_predictions.nar_exploratory_rank_screen import (
        explore_nar_2017_2022_ranking_signal,
    )
    export_summary = {}
    def _optional_export(winner, outsider, metrics):
        nonlocal export_summary
        export_summary = save_nar_exploratory_models_private(
            winner, outsider, metrics, candidate_output_dir,
        )
    m = explore_nar_2017_2022_ranking_signal(
        form, flat_races_by_year=dict(annual), iterations=iterations,
        official_win_payouts_2022=official_2022_win_returns,
        official_place_payouts_2022=official_2022_place_returns,
        on_completed_models=_optional_export if candidate_output_dir is not None else None,
    )
    result = {
        "schema": "NAR.PC2.Exploratory2022RankingSignal.v1",
        **asdict(m),
        "source_months": totals["months"],
        "all_original_races": totals["source"],
        "original_banei_out_of_scope": totals["banei"],
        "historical_form_rows_with_prior_start": audit.target_rows_with_prior_start,
        "historical_form_rows_without_prior_start": audit.target_rows_without_prior_start,
        "original_private_zips_modified": False,
        "preoff_betting_prices_verified": False,
        "historical_complete_coverage": False,
        "source_data_sent_to_github": False,
        "no_prediction_or_source_details_logged": True,
        "trained_model_exported": bool(export_summary),
        "private_model_artifact_hashes_not_logged": True,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-nar-training-zip-directory", type=Path, required=True)
    parser.add_argument("--confirm-personal-private-nar-permission", action="store_true")
    parser.add_argument("--iterations", type=int, default=40)
    parser.add_argument(
        "--candidate-output-dir", type=Path,
        help="OPTIONAL PC2 D: new private research artifact directory",
    )
    args = parser.parse_args()
    try:
        output = screen_private_72_month_exploratory(
            args.local_nar_training_zip_directory,
            permission=args.confirm_personal_private_nar_permission,
            iterations=args.iterations,
            candidate_output_dir=args.candidate_output_dir,
        )
    except Exception as exc:
        # Only immutable source-code error identifiers. Never echo a
        # traceback, private path, source label, horse or race key.
        code = (str(exc) if isinstance(exc, UnsafeNarSource) else "")
        if not re.fullmatch(r"NAR_[A-Z0-9_]{1,100}", code):
            code = "NAR_EXPLORATORY_UNEXPECTED_PRIVATE_FAILURE"
        print(json.dumps({
            "schema": "NAR.PC2.Exploratory2022RankingSignal.v1",
            "status": "NAR_PRIVATE_RETROSPECTIVE_SCREENING_HOLD",
            "staticReason": code,
            "source_data_sent_to_github": False,
            "positive_expected_value_demonstrated": False,
            "protected_final_holdout_opened": False,
        }, sort_keys=True))
        return 2
    print(json.dumps(output, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
