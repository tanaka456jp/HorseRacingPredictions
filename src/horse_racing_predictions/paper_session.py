from dataclasses import dataclass

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
        receipt = self.broker.place(decision)

        bet_id = None
        if receipt.accepted:
            bet_id = self.ledger.record_paper_bet(
                decision,
                prediction_id,
                broker=receipt.broker,
                broker_reference=receipt.reference,
            )

        return PaperEvaluationResult(
            prediction_id=prediction_id,
            decision=decision,
            receipt=receipt,
            bet_id=bet_id,
        )
