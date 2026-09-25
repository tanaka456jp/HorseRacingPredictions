from dataclasses import dataclass, replace
import math

from .broker import ExecutionReceipt, PaperBroker
from .domain import BetDecision, HorsePrediction
from .strategy import decide_win_bet


@dataclass(frozen=True)
class PaperEvaluationResult:
    prediction_id: int
    decision: BetDecision
    receipt: ExecutionReceipt
    bet_id: int | None


class PaperTradingSession:
    def __init__(self, ledger, config, broker=None):
        self.ledger = ledger
        self.config = config
        self.broker = broker or PaperBroker()
        self._day_limits: dict[str, int] = {}
        self._day_stakes: dict[str, int] = {}
        self._race_limits: dict[tuple[str, str], int] = {}
        self._race_stakes: dict[tuple[str, str], int] = {}

    def _round_down(self, value: float) -> int:
        unit = int(self.config.bet_unit_yen)
        if unit <= 0:
            raise ValueError("bet_unit_yen must be positive")
        return int(math.floor(max(0.0, value) / unit) * unit)

    def _day_key(self, snapshot) -> str:
        return snapshot.scheduled_post_time.date().isoformat()

    def _ensure_limits(
        self,
        snapshot,
        bankroll_yen: int,
    ) -> tuple[str, tuple[str, str]]:
        day_key = self._day_key(snapshot)
        race_key = (day_key, snapshot.race_id)

        if day_key not in self._day_limits:
            self._day_limits[day_key] = self._round_down(
                bankroll_yen * self.config.max_day_fraction
            )
            self._day_stakes[day_key] = 0

        if race_key not in self._race_limits:
            self._race_limits[race_key] = self._round_down(
                bankroll_yen * self.config.max_race_fraction
            )
            self._race_stakes[race_key] = 0

        return day_key, race_key

    def _apply_exposure_caps(
        self,
        decision: BetDecision,
        snapshot,
        bankroll_yen: int,
    ) -> BetDecision:
        if decision.stake_yen <= 0:
            return decision

        day_key, race_key = self._ensure_limits(
            snapshot,
            bankroll_yen,
        )
        day_remaining = max(
            0,
            self._day_limits[day_key]
            - self._day_stakes[day_key],
        )
        race_remaining = max(
            0,
            self._race_limits[race_key]
            - self._race_stakes[race_key],
        )
        remaining = min(
            bankroll_yen,
            day_remaining,
            race_remaining,
        )

        capped = self._round_down(
            min(decision.stake_yen, remaining)
        )
        if capped < self.config.min_bet_yen:
            capped = 0

        if capped == decision.stake_yen:
            return decision

        reason = (
            "selected_budget_capped"
            if capped > 0
            else "race_or_day_budget_exhausted"
        )
        return replace(
            decision,
            stake_yen=capped,
            reason=reason,
        )

    def _commit_exposure(
        self,
        snapshot,
        stake_yen: int,
        bankroll_yen: int,
    ) -> None:
        day_key, race_key = self._ensure_limits(
            snapshot,
            bankroll_yen,
        )
        self._day_stakes[day_key] += int(stake_yen)
        self._race_stakes[race_key] += int(stake_yen)

    def exposure_snapshot(self) -> dict:
        return {
            "day_limits": dict(self._day_limits),
            "day_stakes": dict(self._day_stakes),
            "race_limits": dict(self._race_limits),
            "race_stakes": dict(self._race_stakes),
        }

    def evaluate(
        self,
        prediction: HorsePrediction,
        snapshot,
        bankroll_yen: int,
    ) -> PaperEvaluationResult:
        if bankroll_yen <= 0:
            raise ValueError("bankroll_yen must be positive")

        prediction_id = self.ledger.record_paper_prediction(
            prediction,
            snapshot,
        )

        decision = decide_win_bet(
            prediction,
            bankroll_yen,
            self.config,
        )
        decision = self._apply_exposure_caps(
            decision,
            snapshot,
            bankroll_yen,
        )
        receipt = self.broker.place(decision)

        bet_id = None
        if receipt.accepted:
            bet_id = self.ledger.record_paper_bet(
                decision,
                prediction_id,
                broker=receipt.broker,
                broker_reference=receipt.reference,
            )
            self._commit_exposure(
                snapshot,
                decision.stake_yen,
                bankroll_yen,
            )

        return PaperEvaluationResult(
            prediction_id=prediction_id,
            decision=decision,
            receipt=receipt,
            bet_id=bet_id,
        )
