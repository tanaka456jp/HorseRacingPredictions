from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from horse_racing_predictions.jravan_storage_health import (
    inspect_jravan_storage_health,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Report sanitized C/D storage health for the private JRA-VAN archive. "
            "No provider records are opened."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/jravan_storage_health.json"),
    )
    args = parser.parse_args()

    health = inspect_jravan_storage_health()
    payload = asdict(health)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if health.status != "ready":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
