"""Privacy-preserving commitments for PROSPECTIVE NAR forecast batches.

Offline, in-memory and research only: no acquisition, historical 2025+
holdout access, stake, bookmaker, posting, network, file writes or payout.

A random private salt + deterministic SHA256 digest can detect a changed
predeclared roster, candidate ranking, scores, model, schedule or calendar.
It cannot prove WHEN an entry was actually produced. Independent proof
requires a trustworthy third-party publication/receipt of the digest
BEFORE the event. Never assert that a self-supplied predicted_at time or
recomputed hash constitutes contemporaneous external attestation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from math import isfinite
import re
from types import MappingProxyType
from typing import Mapping, Sequence

from .nar_economic_settlement_adapter import nar_canonical_race_id

_JST = timezone(timedelta(hours=9))
_FIRST_PROSPECTIVE = date(2026, 11, 7)
_MAX_FORECASTS = 400
_RACE = re.compile(r"NAR:([0-9]{8}):([^:/\\\r\n]{1,40}):([0-9]{2})\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_DOMAIN = b"HORSE_RACING_PREDICTIONS_NAR_FORWARD_SHA256_V1\x00"


def _utc(value: datetime) -> datetime:
    if (not isinstance(value, datetime) or value.tzinfo is None
            or value.utcoffset() is None):
        raise ValueError("NAR_FORWARD_AWARE_DATETIME_REQUIRED")
    return value.astimezone(timezone.utc)


def _day(text: str) -> date:
    if type(text) is not str:
        raise ValueError("NAR_FORWARD_NONCANONICAL_DATE")
    try:
        out = date.fromisoformat(text)
    except ValueError:
        raise ValueError("NAR_FORWARD_NONCANONICAL_DATE") from None
    if out.isoformat() != text:
        raise ValueError("NAR_FORWARD_NONCANONICAL_DATE")
    return out


def _scores(items: Mapping[str, float]) -> dict[str, str]:
    if (not isinstance(items, Mapping) or
            not 4 <= len(items) <= 18 or
            any(not isinstance(h, str) or not h.strip() or len(h) > 40
                for h in items)):
        raise ValueError("NAR_FORWARD_COMPLETE_HORSE_SCORES_REQUIRED")
    output = {}
    positive = False
    for horse, score in items.items():
        if (type(score) not in (float, int) or
                not isfinite(score) or score < 0 or score > 1e12):
            raise ValueError("NAR_FORWARD_INVALID_SCORE")
        output[horse] = format(float(score), ".17g")
        positive |= score > 0
    if not positive:
        raise ValueError("NAR_FORWARD_ALL_ZERO_SCORES")
    return output


@dataclass(frozen=True)
class NarProspectiveForecast:
    race_id: str = field(repr=False)
    race_day: str
    scheduled_off_utc: datetime = field(repr=False)
    generated_at_utc: datetime = field(repr=False)
    roster_observed_at_utc: datetime = field(repr=False)
    model_source_sha256: str
    model_fit_through_day: str
    winner_scores: Mapping[str, float] = field(repr=False)
    outsider_scores: Mapping[str, float] = field(repr=False)
    market_odds_in_selection: bool = False

    def __post_init__(self) -> None:
        # frozen=True alone does not freeze a nested caller-owned dict.
        object.__setattr__(self, "winner_scores",
                           MappingProxyType(dict(self.winner_scores)))
        object.__setattr__(self, "outsider_scores",
                           MappingProxyType(dict(self.outsider_scores)))


@dataclass(frozen=True)
class NarPrivateForecastCommitment:
    # Digest alone is NOT a public proof; a real timestamped independent
    # witness receipt and complete forecast snapshot are still required.
    sha256_digest: str
    schema: str
    registered_flat_races: int
    locked_forecasts: int
    missing_forecasts: int
    distinct_race_days: int
    predicted_races_contain_final_outcomes: bool = False
    freeze_time_independently_verified: bool = False
    prior_to_result_publication_proven: bool = False
    source_rights_verified: bool = False
    actual_wagers_proven: bool = False
    positive_expected_value_demonstrated: bool = False
    protected_historical_holdout_opened: bool = False


@dataclass(frozen=True)
class NarForwardCommitmentVerification:
    sha256_matches_private_snapshot: bool
    # This flag MUST stay False without independently verified external
    # attestation. Local computed hash never proves creation time.
    independently_timestamped_before_off: bool = False
    legitimate_preoff_roster_verified: bool = False
    authorized_for_realized_roi: bool = False
    positive_expected_value_demonstrated: bool = False


def _canonical_bytes(
    forecasts: Sequence[NarProspectiveForecast],
    expected_races: Mapping[str, str],
) -> bytes:
    if (not isinstance(expected_races, Mapping)
            or not isinstance(forecasts, (tuple, list))
            or not 1 <= len(expected_races) <= _MAX_FORECASTS
            or len(forecasts) != len(expected_races)):
        raise ValueError("NAR_FORWARD_FULL_MANIFEST_REQUIRED")

    calendar = {}
    for race_id, raw_day in expected_races.items():
        if not isinstance(race_id, str) or not (m := _RACE.fullmatch(race_id)):
            raise ValueError("NAR_FORWARD_CANONICAL_RACE_ID_REQUIRED")
        day = _day(raw_day)
        if (day < _FIRST_PROSPECTIVE or
                m.group(1) != day.strftime("%Y%m%d") or
                not 1 <= int(m.group(3)) <= 20):
            raise ValueError("NAR_FORWARD_PROSPECTIVE_DAY_ONLY")
        calendar[race_id] = day

    rows = {}
    versions = set()
    for item in forecasts:
        if not isinstance(item, NarProspectiveForecast):
            raise ValueError("NAR_FORWARD_FROZEN_FORECAST_REQUIRED")
        if item.race_id in rows or item.race_id not in calendar:
            raise ValueError("NAR_FORWARD_DUPLICATE_OR_UNREGISTERED_FORECAST")
        day = calendar[item.race_id]
        if _day(item.race_day) != day:
            raise ValueError("NAR_FORWARD_MANIFEST_RACE_DAY_MISMATCH")
        off = _utc(item.scheduled_off_utc)
        generated = _utc(item.generated_at_utc)
        observed = _utc(item.roster_observed_at_utc)
        if (off.astimezone(_JST).date() != day
                or not observed <= generated < off
                or generated < off - timedelta(days=7)):
            raise ValueError("NAR_FORWARD_PREOFF_CLOCK_SEQUENCE_INVALID")
        fit_day = _day(item.model_fit_through_day)
        if fit_day >= day or not _SHA.fullmatch(item.model_source_sha256):
            raise ValueError("NAR_FORWARD_MODEL_LINEAGE_INVALID")
        if item.market_odds_in_selection:
            raise ValueError("NAR_FORWARD_ODDS_FREE_SELECTION_REQUIRED")
        winners = _scores(item.winner_scores)
        outsiders = _scores(item.outsider_scores)
        if set(winners) != set(outsiders):
            raise ValueError("NAR_FORWARD_SCORE_ROSTERS_DIFFER")
        # All 4 choices are fixed before outcomes can be joined, not
        # calculated from finished ranks or final odds.
        top = sorted(winners, key=lambda horse: (-float(winners[horse]), horse))[:3]
        remaining = sorted(set(winners).difference(top))
        outsider = min(remaining, key=lambda h: (-float(outsiders[h]), h))
        versions.add((item.model_source_sha256, item.model_fit_through_day))
        rows[item.race_id] = {
            "race_id": item.race_id,
            "race_day": item.race_day,
            "scheduled_off_utc": off.isoformat(),
            "generated_at_utc": generated.isoformat(),
            "roster_observed_at_utc": observed.isoformat(),
            "model_source_sha256": item.model_source_sha256,
            "model_fit_through_day": item.model_fit_through_day,
            "winner_scores": winners,
            "outsider_scores": outsiders,
            "top3": top,
            "outsider": outsider,
        }
    if set(rows) != set(calendar):
        raise ValueError("NAR_FORWARD_SELECTIVE_RACE_OMISSION")
    if len(versions) != 1:
        raise ValueError("NAR_FORWARD_MODEL_VERSION_CHANGED_WITHIN_BATCH")

    payload = {
        "schema": "NarPrivateProspectiveCommitment.v1",
        "expected_races": {key: expected_races[key]
                           for key in sorted(expected_races)},
        "forecasts": [rows[key] for key in sorted(rows)],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def seal_nar_prospective_batch(
    expected_races: Mapping[str, str],
    forecasts: Sequence[NarProspectiveForecast],
    *,
    private_salt: bytes,
) -> NarPrivateForecastCommitment:
    """Create a salted private commitment for later independent witnessing.

    Caller MUST keep full private snapshot + secret salt separately. A
    plain digest does not establish pre-off external chronology on its own.
    """
    if type(private_salt) is not bytes or len(private_salt) < 32:
        raise ValueError("NAR_FORWARD_STRONG_PRIVATE_SALT_REQUIRED")
    raw = _canonical_bytes(forecasts, expected_races)
    digest = sha256(_DOMAIN + private_salt + b"\x00" + raw).hexdigest()
    return NarPrivateForecastCommitment(
        sha256_digest=digest,
        schema="NarPrivateProspectiveCommitment.v1",
        registered_flat_races=len(expected_races),
        locked_forecasts=len(forecasts),
        missing_forecasts=0,
        distinct_race_days=len(set(expected_races.values())),
    )


def verify_nar_prospective_batch(
    commitment: NarPrivateForecastCommitment,
    expected_races: Mapping[str, str],
    forecasts: Sequence[NarProspectiveForecast],
    *,
    private_salt: bytes,
) -> NarForwardCommitmentVerification:
    """Local content integrity ONLY, not independently proven timestamp."""
    if (not isinstance(commitment, NarPrivateForecastCommitment)
            or commitment.schema != "NarPrivateProspectiveCommitment.v1"
            or not _SHA.fullmatch(commitment.sha256_digest)
            or commitment.registered_flat_races != len(expected_races)
            or commitment.locked_forecasts != len(forecasts)
            or commitment.missing_forecasts != 0
            or commitment.freeze_time_independently_verified
            or commitment.positive_expected_value_demonstrated):
        raise ValueError("NAR_FORWARD_COMMITMENT_CONTRACT_INVALID")
    again = seal_nar_prospective_batch(
        expected_races, forecasts, private_salt=private_salt,
    )
    return NarForwardCommitmentVerification(
        sha256_matches_private_snapshot=hmac.compare_digest(
            again.sha256_digest, commitment.sha256_digest,
        ),
    )
