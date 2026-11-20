"""PC2-only, 64-bit Python/pywin32 JVOpen auth probe; NO JVGets.

This is a current-week option=2 *authentication* check, not data acquisition.
Never calls JVRead, JVGets, historical setup 3/4, UI properties, or exposes
the licence key. Designed to run as a time-bounded self-hosted child process.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import re
import struct
from typing import Callable

from horse_racing_predictions.jravan import JvLinkClient, JraVanApiError

_CODE = re.compile(r"return code\s+(-?\d+)\b")

@dataclass(frozen=True)
class PythonJvAuthResult:
    schemaVersion: int = 1
    status: str = "BLOCKED"
    stage: str = "NOT_STARTED"
    pythonBits: int = 0
    verifiedPhysicalPC2: bool = False
    jvInitSucceeded: bool = False
    jvOpenAttempted: bool = False
    jvOpenReturnCode: int | None = None
    jvCloseAttempted: bool = False
    jvCloseSucceeded: bool = False
    usageKeyRead: bool = False
    rawRecordsRead: bool = False
    protectedHoldoutOpened: bool = False
    notePostAttempted: bool = False
    publicationAuthorized: bool = False


def _save(report: dict, path: Path) -> None:
    # File contains only fixed fields and numeric JVOpen codes.
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True),
                    encoding="utf-8")


def probe_python64_jvopen(
    *, output: Path, client_factory: Callable[..., JvLinkClient] = JvLinkClient,
    bits: int | None = None, computer: str | None = None,
    windows: bool | None = None,
) -> dict:
    if bits is None:
        bits = struct.calcsize("P") * 8
    if computer is None:
        computer = os.environ.get("COMPUTERNAME", "")
    if windows is None:
        windows = platform.system() == "Windows"
    report = asdict(PythonJvAuthResult(
        pythonBits=bits, verifiedPhysicalPC2=(computer == "DESKTOP-MVV1FD4"),
    ))
    if not windows or computer != "DESKTOP-MVV1FD4" or bits != 64:
        report["stage"] = "WINDOWS_PC2_PYTHON64_REQUIRED"
        _save(report, output)
        return report
    client = None
    try:
        report["stage"] = "COM_DISPATCH"
        _save(report, output)
        client = client_factory(application_id="UNKNOWN")
        report["stage"] = "JVINIT"
        _save(report, output)
        client.initialize()
        report["jvInitSucceeded"] = True
        report["stage"] = "JVOPEN_CURRENT_WEEK"
        report["jvOpenAttempted"] = True
        _save(report, output)
        open_result = client.open_race(
            from_time="00000000000000", option=2,
        )
        report["jvOpenReturnCode"] = int(open_result.return_code)
        report["stage"] = "JVOPEN_RETURNED"
        report["status"] = "JVOPEN_AUTHENTICATED" if open_result.return_code >= 0 else "JVOPEN_REFUSED"
    except Exception as exc:
        # Discard exception text/tracebacks: may contain user paths or keys.
        if isinstance(exc, JraVanApiError):
            match = _CODE.search(str(exc))
            if match:
                report["jvOpenReturnCode"] = int(match.group(1))
                report["stage"] = "JVOPEN_RETURNED_ERROR_CODE"
        report["status"] = "BLOCKED"
    finally:
        if client is not None:
            report["jvCloseAttempted"] = True
            try:
                client.close()
                report["jvCloseSucceeded"] = True
            except Exception:
                report["status"] = "BLOCKED"
                report["stage"] = "JVCLOSE_FAILED"
        # Closing must be confirmed before reporting a successful connection.
        if not report["jvCloseSucceeded"]:
            report["status"] = "BLOCKED"
        _save(report, output)
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    # Never print a potentially non-sanitized exception.
    probe_python64_jvopen(output=args.output)


if __name__ == "__main__":
    main()
