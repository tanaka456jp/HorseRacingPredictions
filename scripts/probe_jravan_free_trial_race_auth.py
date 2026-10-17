from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import platform
import re
import struct
import sys
from pathlib import Path

from horse_racing_predictions.jravan import (
    JraVanApiError,
    JraVanUnavailableError,
    JvLinkClient,
)
from horse_racing_predictions.jravan_free_trial_archive import (
    DEFAULT_ARCHIVE_RANGE,
)


@dataclass(frozen=True)
class ProbeResult:
    status: str
    dataspec: str
    jvopen_range: str
    option: int
    sid: str
    initialized: bool
    return_code: int | None
    read_count: int
    download_count: int
    last_file_timestamp: str
    raw_records_read: bool
    error: str | None


def _code(message: str) -> int | None:
    match = re.search(r"return code\s+(-?\d+)", message)
    return int(match.group(1)) if match else None


def probe_dataspec(
    dataspec: str,
    *,
    jvopen_range: str = DEFAULT_ARCHIVE_RANGE,
    option: int = 4,
    sid: str = "UNKNOWN",
) -> ProbeResult:
    client = None
    initialized = False
    try:
        client = JvLinkClient(application_id=sid)
        client.initialize()
        initialized = True
        opened = client.open_data(
            dataspec=dataspec,
            from_time=jvopen_range,
            option=option,
        )
        return ProbeResult(
            status=(
                "no_data"
                if opened.return_code == -1
                else "open_succeeded"
            ),
            dataspec=dataspec,
            jvopen_range=jvopen_range,
            option=option,
            sid=sid,
            initialized=True,
            return_code=opened.return_code,
            read_count=opened.read_count,
            download_count=opened.download_count,
            last_file_timestamp=opened.last_file_timestamp,
            raw_records_read=False,
            error=None,
        )
    except (JraVanApiError, JraVanUnavailableError, ValueError) as exc:
        message = str(exc)
        return ProbeResult(
            status="blocked",
            dataspec=dataspec,
            jvopen_range=jvopen_range,
            option=option,
            sid=sid,
            initialized=initialized,
            return_code=_code(message),
            read_count=0,
            download_count=0,
            last_file_timestamp="",
            raw_records_read=False,
            error=message,
        )
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sanitized JV-Link free-trial auth probe. Opens metadata only; "
            "never reads raw records."
        )
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/jravan_race_auth_probe.json"),
    )
    args = parser.parse_args()

    control = probe_dataspec("HOSN")
    race = probe_dataspec("RACE")

    if (
        control.return_code == -1
        and race.return_code == -301
        and control.initialized
        and race.initialized
    ):
        interpretation = (
            "JVInit/COM path is functional and a non-RACE JVOpen reaches the "
            "provider, while RACE is rejected with authentication code -301. "
            "Do not loop retries or buy/renew service automatically; verify "
            "RACE in the official JRA-VAN sample/validation tool on this PC."
        )
    elif race.return_code == -301:
        interpretation = (
            "RACE is rejected with JVOpen -301. Official JRA-VAN guidance "
            "classifies -301 as an authentication/usage-key error. No paid "
            "action is authorized by this probe."
        )
    elif race.status == "open_succeeded":
        interpretation = (
            "RACE JVOpen now succeeds. A separate bounded archive workflow may "
            "be used to preserve pre-2025 RACE data on the D drive."
        )
    else:
        interpretation = (
            "Probe result is inconclusive; inspect sanitized codes without "
            "reading raw records or changing service entitlement."
        )

    payload = {
        "status": "sanitized_probe_complete",
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "python_bits": struct.calcsize("P") * 8,
        "application_sid": "UNKNOWN",
        "provider_bound": DEFAULT_ARCHIVE_RANGE,
        "raw_records_read": False,
        "control": asdict(control),
        "race": asdict(race),
        "interpretation": interpretation,
        "paid_action_authorized": False,
        "protected_holdout": "2025-2026 untouched",
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
