from dataclasses import dataclass
import math

@dataclass(frozen=True)
class ModelEvaluation:
    model_version: str
    n: int
    log_loss: float
    brier: float
    roi: float
    max_drawdown: float

def brier_score(probabilities, outcomes):
    vals = [(float(p)-float(y))**2 for p,y in zip(probabilities,outcomes)]
    return sum(vals)/len(vals) if vals else float("nan")

def binary_log_loss(probabilities, outcomes, eps=1e-12):
    vals = []
    for p,y in zip(probabilities,outcomes):
        p = min(1-eps,max(eps,float(p)))
        y = float(y)
        vals.append(-(y*math.log(p)+(1-y)*math.log(1-p)))
    return sum(vals)/len(vals) if vals else float("nan")

def challenger_can_promote(champion, challenger, min_samples=500):
    reasons = []
    if challenger.n < min_samples:
        reasons.append("insufficient_oos_samples")
    if challenger.log_loss >= champion.log_loss:
        reasons.append("log_loss_not_better")
    if challenger.brier >= champion.brier:
        reasons.append("brier_not_better")
    if challenger.max_drawdown > champion.max_drawdown:
        reasons.append("drawdown_worse")
    return len(reasons) == 0, reasons
