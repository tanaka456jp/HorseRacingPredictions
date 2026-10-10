"""JRA-VAN exotic-odds evidence policy for strict prebet EV research.

This module encodes the JVData-spec distinction that must not be blurred:

- RACE/setup record O5: final trio odds (確定オッズ)
- RACE/setup record O6: final trifecta odds (確定オッズ)
- realtime dataspec 0B35: current trio速報 odds
- realtime dataspec 0B36: current trifecta速報 odds
- historical time-series dataspecs 0B41/0B42 cover O1/O2 only, not trio/trifecta

Therefore setup O5/O6 can be useful for market-description research but MUST NOT
be treated as an executable pre-decision price or used for strict prebet EV.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


PROTECTED_HOLDOUT_START = date(2025, 1, 1)
PROTECTED_HOLDOUT_END = date(2026, 12, 31)

FINAL_EXOTIC_RECORDS = {
    "O5": "trio",
    "O6": "trifecta",
}
REALTIME_EXOTIC_DATASPECS = {
    "0B35": "trio",
    "0B36": "trifecta",
}
HISTORICAL_TIME_SERIES_DATASPECS = {
    "0B41": "win_place_bracket",
    "0B42": "quinella",
}


@dataclass(frozen=True)
class ExoticOddsEvidencePolicy:
    source_code: str
    bet_type: str | None
    evidence_kind: str
    can_be_prebet_quote: bool
    can_be_strict_ev_input: bool
    protected_holdout_blocked: bool
    reason: str


def classify_jv_odds_evidence(
    source_code: str,
    *,
    race_date: date | None = None,
) -> ExoticOddsEvidencePolicy:
    """Classify only the evidence type; never authorize acquisition or staking."""
    code = str(source_code).strip().upper()

    if code in FINAL_EXOTIC_RECORDS:
        return ExoticOddsEvidencePolicy(
            source_code=code,
            bet_type=FINAL_EXOTIC_RECORDS[code],
            evidence_kind="final_odds",
            can_be_prebet_quote=False,
            can_be_strict_ev_input=False,
            protected_holdout_blocked=False,
            reason=(
                "JVData RACE/setup O5/O6 are final odds; final odds are "
                "forbidden as purchase-time evidence."
            ),
        )

    if code in HISTORICAL_TIME_SERIES_DATASPECS:
        return ExoticOddsEvidencePolicy(
            source_code=code,
            bet_type=None,
            evidence_kind="historical_time_series_non_exotic",
            can_be_prebet_quote=False,
            can_be_strict_ev_input=False,
            protected_holdout_blocked=False,
            reason=(
                "JVData 0B41/0B42 time-series cover O1/O2 markets, not "
                "trio/trifecta."
            ),
        )

    if code in REALTIME_EXOTIC_DATASPECS:
        protected = bool(
            race_date is not None
            and PROTECTED_HOLDOUT_START
            <= race_date
            <= PROTECTED_HOLDOUT_END
        )
        return ExoticOddsEvidencePolicy(
            source_code=code,
            bet_type=REALTIME_EXOTIC_DATASPECS[code],
            evidence_kind="realtime_exotic_snapshot",
            can_be_prebet_quote=not protected,
            can_be_strict_ev_input=False,
            protected_holdout_blocked=protected,
            reason=(
                "Protected 2025-2026 final holdout: realtime exotic market "
                "data must not be read or collected."
                if protected
                else (
                    "Realtime 0B35/0B36 can become prebet quote evidence only "
                    "after lawful local capture, immutable timestamps, purchase-"
                    "cutoff verification, source-rights review, and strict-OOS "
                    "protocol approval. Classification alone never approves EV."
                )
            ),
        )

    return ExoticOddsEvidencePolicy(
        source_code=code,
        bet_type=None,
        evidence_kind="unknown",
        can_be_prebet_quote=False,
        can_be_strict_ev_input=False,
        protected_holdout_blocked=False,
        reason="Unknown JV odds evidence is fail-closed.",
    )
