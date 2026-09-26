from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

from .config import StrategyConfig
from .data_sources import (
    load_future_entries_csv,
    load_jra_history_csv,
)
from .inference import predict_future_entries
from .model_artifact import load_champion_artifact
from .odds_provider import CsvOddsSnapshotProvider
from .paper_cli import run_paper_csv
from .paper_input import prepare_paper_input


def run_forward_paper_pipeline(
    *,
    history_path: str | Path,
    entries_path: str | Path,
    artifact_dir: str | Path,
    odds_path: str | Path,
    ledger_path: str | Path,
    output_dir: str | Path,
    bankroll_yen: int,
    decision_time: datetime | None = None,
    config: StrategyConfig | None = None,
) -> dict:
    if bankroll_yen <= 0:
        raise ValueError("bankroll_yen must be positive")

    decision_time = decision_time or datetime.now(timezone.utc)
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("decision_time must be timezone-aware")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    champion = load_champion_artifact(artifact_dir)
    history = load_jra_history_csv(history_path)
    entries = load_future_entries_csv(entries_path)

    predictions = predict_future_entries(
        champion,
        history,
        entries,
    )
    predictions_path = output_dir / "future_predictions.csv"
    predictions.to_csv(
        predictions_path,
        index=False,
        encoding="utf-8-sig",
    )

    provider = CsvOddsSnapshotProvider(odds_path)
    paper_input = prepare_paper_input(
        predictions,
        provider,
        decision_time,
    )
    paper_input_path = output_dir / "paper_input.csv"
    paper_input.to_csv(
        paper_input_path,
        index=False,
        encoding="utf-8-sig",
    )

    paper_result = run_paper_csv(
        paper_input_path,
        ledger_path,
        bankroll_yen,
        config=config,
    )

    summary = {
        "mode": "forward_paper_only",
        "model_version": champion.manifest.model_version,
        "experiment_id": champion.manifest.experiment_id,
        "history_cutoff": champion.manifest.train_end,
        "decision_time": decision_time.isoformat(),
        "predictions_file": str(predictions_path),
        "paper_input_file": str(paper_input_path),
        "ledger_file": str(ledger_path),
        "paper_result": paper_result,
    }

    summary_path = output_dir / "forward_paper_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary["summary_file"] = str(summary_path)
    return summary
