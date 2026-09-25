from dataclasses import dataclass

PRE_RACE_SNAPSHOT = "pre_race_snapshot"
FINAL_WIN_ODDS = "final_win_odds"
ESTIMATED_ODDS = "estimated_odds"

VALID_ODDS_EVIDENCE = {
    PRE_RACE_SNAPSHOT,
    FINAL_WIN_ODDS,
    ESTIMATED_ODDS,
}

@dataclass(frozen=True)
class ValidationEvidence:
    odds_evidence: str
    roi_verified: bool
    label: str

def classify_odds_evidence(odds_evidence: str) -> ValidationEvidence:
    if odds_evidence not in VALID_ODDS_EVIDENCE:
        raise ValueError(
            f"unknown odds evidence: {odds_evidence}; "
            f"expected one of {sorted(VALID_ODDS_EVIDENCE)}"
        )
    if odds_evidence == PRE_RACE_SNAPSHOT:
        return ValidationEvidence(
            odds_evidence=odds_evidence,
            roi_verified=True,
            label="verified_pre_race_odds",
        )
    if odds_evidence == FINAL_WIN_ODDS:
        return ValidationEvidence(
            odds_evidence=odds_evidence,
            roi_verified=False,
            label="research_only_final_odds",
        )
    return ValidationEvidence(
        odds_evidence=odds_evidence,
        roi_verified=False,
        label="research_only_estimated_odds",
    )
