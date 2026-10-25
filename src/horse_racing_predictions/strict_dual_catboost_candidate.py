"""Build TWO independently fitted non-market CatBoost research candidates.

Only approved pre-2025 history may be supplied. Separate later pre-2025
validation measures winner and podium-outsider performance; a model file is
not itself evidence of licensing, model provenance, calibration, positive
expected value or permission to post on note.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from math import isfinite, log
from pathlib import Path
import re

import numpy as np
import pandas as pd

from .modeling import CatBoostProbabilityModel
from .odds_free_chronological_eval import (
    _MARKET, _check_race_groups, _strict_date, _validate_research_features,
)
from .odds_free_training import OddsFreeResearchSample

FINAL_START = date(2025, 1, 1)
_ALLOWED_SOURCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{2,160}\Z")


@dataclass(frozen=True)
class StrictDualCatboostMetrics:
    status: str
    winModelTarget: str
    outsiderModelTarget: str
    fitThrough: str
    validationFrom: str
    validationThrough: str
    trainingRaces: int
    validationRaces: int
    trainingRunners: int
    validationRunners: int
    featureCount: int
    winTop1Accuracy: float
    winTop3Coverage: float
    winnerLogLoss: float
    winnerBrier: float
    outsiderCandidateHitTop3Rate: float
    winRankFourthHitTop3Rate: float
    improvementOverFourth: float
    sourceRightsIndependentlyVerified: bool
    upstreamMarketIndependentSamplingVerified: bool
    outsiderFrozenAndIndependentlyVerified: bool
    publicationAuthorized: bool
    positiveExpectedValueDemonstrated: bool


@dataclass
class StrictDualCatboostCandidate:
    winner: CatBoostProbabilityModel
    outsider: CatBoostProbabilityModel
    features: tuple[str, ...]
    metrics: StrictDualCatboostMetrics
    train_start: str


def _validate(sample: OddsFreeResearchSample, *, fit: date, start: date, end: date):
    if not fit < start <= end < FINAL_START:
        raise ValueError("fold dates must be strictly chronological before final holdout")
    if not isinstance(sample, OddsFreeResearchSample):
        raise ValueError("approved non-market sample required")
    _validate_research_features(sample.features)
    if _strict_date(sample.cutoff, "sample cutoff") >= FINAL_START:
        raise ValueError("protected final holdout forbidden")
    if _strict_date(sample.cutoff, "sample cutoff") < end:
        raise ValueError("validation period not covered")
    df = sample.frame.copy()
    if df.columns.duplicated().any() or any(
        _MARKET.search(str(c)) for c in df.columns
    ):
        raise ValueError("duplicate or market-dependent input column")
    required = {"race_id", "race_date", "horse_name", "finish_position", "is_winner"}
    if not required.issubset(df) or not set(sample.features).issubset(df):
        raise ValueError("required non-market inputs or labels missing")
    df["race_date"] = pd.to_datetime(df["race_date"], errors="raise")
    if (df["race_date"].isna().any() or df["race_date"].dt.tz is not None
            or df["race_date"].dt.date.ge(FINAL_START).any()):
        raise ValueError("protected final holdout / invalid dates")
    finish = pd.to_numeric(df["finish_position"], errors="coerce")
    win = pd.to_numeric(df["is_winner"], errors="coerce")
    if (finish.isna().any() or win.isna().any()
            or not win.eq(finish.eq(1).astype(int)).all()):
        raise ValueError("inconsistent target results")
    train = df.loc[df["race_date"].dt.date.le(fit)].copy()
    valid = df.loc[df["race_date"].dt.date.between(start, end)].copy()
    if train.empty or valid.empty or set(train["race_id"]) & set(valid["race_id"]):
        raise ValueError("training and validation overlap or missing")
    if _check_race_groups(train, require_podium=True) < 5:
        raise ValueError("not enough independent training races")
    if _check_race_groups(valid, require_podium=True) < 3:
        raise ValueError("not enough independent validation races")
    return train, valid


def fit_strict_dual_catboost_candidate(
    sample: OddsFreeResearchSample, *,
    fit_through: str, validation_from: str, validation_through: str,
    iterations: int = 100,
) -> StrictDualCatboostCandidate:
    """Fit actual CatBoost models on training fold; test only on later races."""
    fit = _strict_date(fit_through, "fit_through")
    start = _strict_date(validation_from, "validation_from")
    end = _strict_date(validation_through, "validation_through")
    if not isinstance(iterations, int) or not 30 <= iterations <= 600:
        raise ValueError("candidate iterations must be between 30 and 600")
    train, valid = _validate(sample, fit=fit, start=start, end=end)
    winner = CatBoostProbabilityModel(
        feature_columns=list(sample.features), iterations=iterations,
    )
    outsider = CatBoostProbabilityModel(
        feature_columns=list(sample.features), iterations=iterations,
    )
    # The podium model is separately fitted from a different target.
    train["__podium_label_train_only"] = (
        train["finish_position"].astype(int).le(3).astype(int)
    )
    winner.fit(train, target_col="is_winner")
    outsider.fit(train, target_col="__podium_label_train_only")
    if winner.model is outsider.model or winner.model is None or outsider.model is None:
        raise ValueError("two independently fitted CatBoost binaries required")
    unseen = valid.drop(columns=[
        "finish_position", "is_winner", "__podium_label_train_only",
        "finish_time", "margin", "last_3f", "corner_1", "corner_2",
        "corner_3", "corner_4", "prize_money",
    ], errors="ignore")
    win_prob = winner.predict_win_probability(unseen, race_col="race_id")
    outsider_score = outsider.predict_win_probability(unseen, race_col="race_id")
    if (not win_prob.index.equals(valid.index)
            or not outsider_score.index.equals(valid.index)
            or not np.isfinite(win_prob.to_numpy(dtype=float)).all()
            or not np.isfinite(outsider_score.to_numpy(dtype=float)).all()
            or win_prob.le(0).any() or outsider_score.le(0).any()):
        raise ValueError("invalid held-out CatBoost inference")
    for result in (win_prob, outsider_score):
        if not np.allclose(
            result.groupby(valid["race_id"]).sum().to_numpy(dtype=float),
            1.0, atol=1e-9,
        ):
            raise ValueError("race probabilities not normalized")
    predicted = unseen[["race_id", "horse_name"]].copy()
    predicted["__win"] = win_prob
    predicted["__podium_score"] = outsider_score
    true_finishes = valid.set_index(["race_id", "horse_name"])[
        "finish_position"
    ]
    correct_winner = podium_overlap = outsider_hits = fourth_hits = 0.0
    winner_log_loss = 0.0
    for rid, race in predicted.groupby("race_id", sort=False):
        rank = race.sort_values(
            ["__win", "horse_name"], ascending=[False, True], kind="stable",
        )
        actual = valid.loc[valid["race_id"].eq(rid)].sort_values(
            ["finish_position", "horse_name"], kind="stable",
        )
        ranked_names = rank["horse_name"].astype(str).tolist()
        actual_names = actual["horse_name"].astype(str).tolist()
        top3 = set(ranked_names[:3])
        podium = set(actual_names[:3])
        correct_winner += int(ranked_names[0] == actual_names[0])
        podium_overlap += len(top3 & podium) / 3.0
        allowed = rank.loc[~rank["horse_name"].astype(str).isin(top3)]
        outsider_pick = allowed.sort_values(
            ["__podium_score", "horse_name"], ascending=[False, True],
            kind="stable",
        ).iloc[0]["horse_name"]
        outsider_hits += int(true_finishes.loc[(rid, outsider_pick)] <= 3)
        fourth_hits += int(true_finishes.loc[(rid, ranked_names[3])] <= 3)
        winner_log_loss -= log(float(
            rank.loc[rank["horse_name"].eq(actual_names[0]), "__win"].iloc[0]
        ))
    n = valid["race_id"].nunique()
    brier = float(np.square(
        win_prob.to_numpy(dtype=float) - valid["is_winner"].to_numpy(dtype=float)
    ).mean())
    values = (
        correct_winner / n, podium_overlap / n, winner_log_loss / n, brier,
        outsider_hits / n, fourth_hits / n,
    )
    if not all(isfinite(v) for v in values):
        raise ValueError("nonfinite research metric")
    metrics = StrictDualCatboostMetrics(
        status="RESEARCH_ONLY_NOT_PUBLISHED",
        winModelTarget="is_winner",
        outsiderModelTarget="finish_position_le_3_train_only",
        fitThrough=fit.isoformat(),
        validationFrom=start.isoformat(),
        validationThrough=end.isoformat(),
        trainingRaces=train["race_id"].nunique(),
        validationRaces=n,
        trainingRunners=len(train), validationRunners=len(valid),
        featureCount=len(sample.features),
        winTop1Accuracy=values[0], winTop3Coverage=values[1],
        winnerLogLoss=values[2], winnerBrier=values[3],
        outsiderCandidateHitTop3Rate=values[4],
        winRankFourthHitTop3Rate=values[5],
        improvementOverFourth=values[4] - values[5],
        sourceRightsIndependentlyVerified=False,
        upstreamMarketIndependentSamplingVerified=False,
        outsiderFrozenAndIndependentlyVerified=False,
        publicationAuthorized=False,
        positiveExpectedValueDemonstrated=False,
    )
    return StrictDualCatboostCandidate(
        winner=winner, outsider=outsider,
        features=tuple(sample.features), metrics=metrics,
        train_start=train["race_date"].min().date().isoformat(),
    )


def save_dual_candidate_for_research(
    candidate: StrictDualCatboostCandidate, *, destination: Path,
    source_ref: str,
) -> dict:
    """Write only a NEW research directory; never replace protected artifacts."""
    if not isinstance(destination, Path) or not destination.is_absolute():
        raise ValueError("explicit absolute research path required")
    if (destination.is_symlink() or destination.exists()
            or destination.parent.is_symlink()
            or not destination.parent.is_dir()):
        raise ValueError("destination must be a fresh dir under existing parent")
    if not isinstance(source_ref, str) or not _ALLOWED_SOURCE.fullmatch(source_ref):
        raise ValueError("non-sensitive source reference ID required")
    if (not isinstance(candidate, StrictDualCatboostCandidate)
            or candidate.metrics.publicationAuthorized
            or candidate.metrics.positiveExpectedValueDemonstrated):
        raise ValueError("only non-publishable research candidates are supported")
    destination.mkdir()
    hashes: dict[str, str] = {}
    for name, wrapper in (
        ("win.cbm", candidate.winner),
        ("outsider.cbm", candidate.outsider),
    ):
        path = destination / name
        if wrapper.model is None:
            raise ValueError("trained native model missing")
        wrapper.model.save_model(str(path))
        hashes[name] = sha256(path.read_bytes()).hexdigest()
    manifest = {
        "schemaVersion": 1,
        "artifactKind": "dual-catboost-oddsfree-research-candidate",
        "status": "RESEARCH_NOT_APPROVED_FOR_PUBLICATION",
        "sourceRef": source_ref,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "featureColumns": list(candidate.features),
        "trainStart": candidate.train_start,
        "trainEnd": candidate.metrics.fitThrough,
        "artifactSha256": hashes,
        "researchMetrics": asdict(candidate.metrics),
        "publicationAuthorized": False,
        "retrainingOnProtectedHoldoutAllowed": False,
        "sourceRightsIndependentlyVerified": False,
        "independentOutsiderModelVerified": False,
        "modelRuntimeProvenanceVerified": False,
    }
    (destination / "candidate_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return {
        "status": "RESEARCH_ARTIFACT_SAVED_NOT_APPROVED",
        "artifactSha256": hashes, "publicationAuthorized": False,
    }
