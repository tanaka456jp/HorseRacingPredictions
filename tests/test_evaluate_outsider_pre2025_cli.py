"""Exercise only local fictional CSV; no real horses, JRA-VAN or note."""
from __future__ import annotations

from datetime import date, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import json
import sys

import pandas as pd

# scripts/ is a CLI directory, not an installed Python package.
script = Path(__file__).resolve().parents[1] / "scripts" / "evaluate_outsider_pre2025_local.py"
spec = spec_from_file_location("evaluate_outsider_pre2025_local", script)
assert spec is not None and spec.loader is not None
cli = module_from_spec(spec)
spec.loader.exec_module(cli)


def _args(path):
    return [
        "evaluate_outsider_pre2025_local.py", "--history-csv", str(path),
        "--train-start", "2022-06-01",
        "--train-end", "2022-06-18",
        "--fit-through", "2022-06-10",
        "--validation-from", "2022-06-11",
        "--validation-through", "2022-06-18",
    ]


def _synthetic():
    rows = []
    for r in range(18):
        race_day = (date(2022, 6, 1) + timedelta(days=r)).isoformat()
        for h in range(1, 7):
            rows.append({
                "race_id": f"FAKE-{r}",
                "race_date": race_day,
                "horse_name": f"架空馬{h}",
                "finish_position": (r + h) % 6 + 1,
                "distance_m": 1200 + (r % 3) * 200,
                "age": 3 + h % 4,
                "post_position": h,
                "carried_weight": 53 + h % 3,
                "win_odds": h + 1,
            })
    return pd.DataFrame(rows)


def test_cli_fails_closed_without_file(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(sys, "argv", _args(tmp_path / "missing.csv"))
    assert cli.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["publicationAuthorized"] is False


def test_cli_runs_real_estimator_on_fictional_pre2025_rows(tmp_path, monkeypatch, capsys):
    file = tmp_path / "fictional.csv"
    _synthetic().to_csv(file, index=False)
    monkeypatch.setattr(sys, "argv", _args(file))
    assert cli.main() == 0
    stdout = capsys.readouterr().out
    result = json.loads(stdout)
    assert result["validationRaces"] == 8
    assert result["status"] == "RESEARCH_ONLY_NOT_FROZEN_NOT_PUBLISHABLE"
    assert result["publicationAuthorized"] is False
    assert result["positiveExpectedValueDemonstrated"] is False
    assert "架空馬" not in stdout
    assert str(file) not in stdout


def test_cli_rejects_protected_2025_2026_rows(tmp_path, monkeypatch, capsys):
    file = tmp_path / "protected.csv"
    data = _synthetic()
    protected = data.iloc[[0]].copy()
    protected["race_id"] = "HOLDOUT"
    protected["race_date"] = "2026-10-24"
    pd.concat([data, protected], ignore_index=True).to_csv(file, index=False)
    monkeypatch.setattr(sys, "argv", _args(file))
    assert cli.main() == 2
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "BLOCKED"
    assert result["publicationAuthorized"] is False
