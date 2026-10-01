from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess


FROZEN_FILES = {
    "src/horse_racing_predictions/residual_shadow_paper.py",
    "src/horse_racing_predictions/residual_paper_evidence.py",
    "src/horse_racing_predictions/market_residual_v12_holdout.py",
    "src/horse_racing_predictions/residual_v12_artifact.py",
}
INFRASTRUCTURE_FILES = {
    "scripts/verify_autonomous_dev_guard.py",
    "scripts/run_autonomous_dev_cycle.ps1",
    "scripts/run_autonomous_dev_12h.ps1",
}
FORBIDDEN_PREFIXES = (
    ".github/workflows/",
    "data/",
    "artifacts/",
    "secrets/",
)
FORBIDDEN_SUFFIXES = (
    ".sqlite",
    ".sqlite3",
    ".db",
)
EXPECTED_CONSTANTS = {
    "src/horse_racing_predictions/residual_shadow_paper.py": {
        "PAPER_MIN_EV": 1.15,
        "PAPER_MIN_PROBABILITY": 0.03,
        "PAPER_FRACTIONAL_KELLY": 0.25,
        "PAPER_MAX_RACE_FRACTION": 0.02,
        "PAPER_MAX_DAY_FRACTION": 0.08,
        "PAPER_MAX_BET_YEN": 10_000,
        "PAPER_MIN_BET_YEN": 100,
        "PAPER_BET_UNIT_YEN": 100,
        "PAPER_MAX_ODDS_AGE_MINUTES": 10,
    },
    "src/horse_racing_predictions/residual_paper_evidence.py": {
        "MIN_PROSPECTIVE_EVALUATED_RACES": 500,
        "MIN_SETTLED_PAPER_BETS": 200,
        "ROI_BOOTSTRAP_REPLICATES": 5_000,
        "ROI_BOOTSTRAP_SEED": 20260930,
        "ROI_CONFIDENCE_LEVEL": 0.95,
    },
    "src/horse_racing_predictions/market_residual_v12_holdout.py": {
        "FIXED_GAMMA": 4.0,
    },
}


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _changed_files(repo: Path) -> list[str]:
    output = _git(repo, "diff", "--name-only", "origin/main")
    return [
        line.strip().replace("\\", "/")
        for line in output.splitlines()
        if line.strip()
    ]


def _assignments(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            values[target.id] = ast.literal_eval(node.value)
        except Exception:
            continue
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()

    changed = _changed_files(repo)
    errors: list[str] = []
    if not changed:
        errors.append("Codex produced no tracked repository changes.")

    for rel in changed:
        lower = rel.lower()
        if rel in FROZEN_FILES:
            errors.append(f"Frozen policy/model file changed: {rel}")
        if rel in INFRASTRUCTURE_FILES:
            errors.append(f"Autonomous guard/orchestrator changed itself: {rel}")
        if any(rel.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            errors.append(f"Forbidden path changed: {rel}")
        if "holdout" in lower:
            errors.append(f"Holdout path changed: {rel}")
        if lower.endswith(FORBIDDEN_SUFFIXES):
            errors.append(f"Database file changed: {rel}")
        if lower.endswith(".env") or "/.env" in lower:
            errors.append(f"Environment/secret file changed: {rel}")

        path = repo / rel
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = ""
            if re.search(r"live_execution_enabled\s*=\s*True", text):
                errors.append(f"Live execution enablement found in: {rel}")
            if re.search(r"automatic_live_promotion\s*=\s*True", text):
                errors.append(f"Automatic live promotion found in: {rel}")

    for rel, expected in EXPECTED_CONSTANTS.items():
        values = _assignments(repo / rel)
        for name, expected_value in expected.items():
            actual = values.get(name, object())
            if actual != expected_value:
                errors.append(
                    f"Frozen constant mismatch {rel}:{name}: "
                    f"expected={expected_value!r} actual={actual!r}"
                )

    report = {
        "status": "pass" if not errors else "fail",
        "changed_files": changed,
        "errors": errors,
        "frozen_policy_preserved": not errors,
        "live_execution_enabled": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
