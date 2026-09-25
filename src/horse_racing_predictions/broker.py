from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionReceipt:
    accepted: bool
    broker: str
    reference: str
    message: str

class PaperBroker:
    def place(self, decision):
        if decision.stake_yen <= 0:
            return ExecutionReceipt(False, "paper", "", "no bet")
        ref = f"PAPER:{decision.race_id}:{decision.horse_id}:{decision.stake_yen}"
        return ExecutionReceipt(True, "paper", ref, "paper bet accepted")

class LiveBroker:
    def place(self, decision):
        raise RuntimeError(
            "Live execution is disabled in Phase 1. "
            "Paper Tradingと検証基準を通過するまで有効化しません。"
        )
