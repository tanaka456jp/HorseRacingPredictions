from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import json
import platform
import re
import struct
import sys
from pathlib import Path

from .jravan import (
    JraVanApiError,
    JraVanUnavailableError,
    JvLinkClient,
)


ERROR_GUIDANCE = {
    -112: (
        "fromtime is invalid. Use a 14-digit data-provision timestamp "
        "such as 20210801000000."
    ),
    -115: "JVOpen option is invalid.",
    -116: "The dataspec/option combination is invalid.",
    -201: "JVInit was not completed before JVOpen.",
    -202: "A prior JVOpen/JVRTOpen was not closed with JVClose.",
    -211: (
        "JV-Link registry state is invalid. Re-open JV-Link settings "
        "or reinstall JV-Link if necessary."
    ),
    -301: (
        "Authentication error. First confirm the official Data Lab "
        "validation/sample tool works on the same PC. If the official "
        "tool succeeds but Python fails, preserve this doctor report."
    ),
    -302: "The Data Lab service right has expired.",
    -303: (
        "No usage key is configured. Open JV-Link settings and confirm "
        "the free-trial/service state."
    ),
    -305: (
        "The Data Lab terms have not been accepted. Open JV-Link "
        "settings and complete the required agreement."
    ),
}


@dataclass(frozen=True)
class JraVanDoctorReport:
    status: str
    platform: str
    python_version: str
    python_bits: int
    sid: str
    from_time: str
    option: int
    initialized: bool
    status_before_open: int | None
    open_return_code: int | None
    read_count: int
    download_count: int
    last_file_timestamp: str
    sample_records: int
    record_type_counts: dict[str, int]
    ra_records: int
    se_records: int
    errors: tuple[str, ...]
    guidance: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return self.status in {
            "ready",
            "connected_no_ra_se",
        }


def _extract_code(message: str) -> int | None:
    match = re.search(r"return code\s+(-?\d+)", message)
    if not match:
        return None
    return int(match.group(1))


def _guidance_for_code(code: int | None) -> str | None:
    if code is None:
        return None
    return ERROR_GUIDANCE.get(
        code,
        f"JV-Link returned code {code}. Check the current "
        "JV-Link interface specification/error-code table.",
    )


def run_jravan_doctor(
    *,
    from_time: str = "20210801000000",
    option: int = 4,
    sid: str = "UNKNOWN",
    max_records: int = 1000,
    client: JvLinkClient | None = None,
) -> JraVanDoctorReport:
    if max_records < 1:
        raise ValueError("max_records must be positive")

    errors: list[str] = []
    guidance: list[str] = []
    counts: Counter[str] = Counter()
    initialized = False
    status_before_open = None
    open_code = None
    read_count = 0
    download_count = 0
    last_file_timestamp = ""

    own_client = client is None
    try:
        if client is None:
            client = JvLinkClient(application_id=sid)

        client.initialize()
        initialized = True

        try:
            status_before_open = client.status()
            if status_before_open == -203:
                guidance.append(
                    "JVStatus=-203 before JVOpen is expected because no "
                    "download/read operation has started yet."
                )
        except Exception as exc:
            guidance.append(
                f"JVStatus pre-check was unavailable: {exc}"
            )

        opened = client.open_race(
            from_time=from_time,
            option=option,
        )
        open_code = opened.return_code
        read_count = opened.read_count
        download_count = opened.download_count
        last_file_timestamp = opened.last_file_timestamp

        for record in client.iter_records():
            counts[record.record_type] += 1
            if sum(counts.values()) >= max_records:
                break

        sample_records = sum(counts.values())
        ra_count = counts.get("RA", 0)
        se_count = counts.get("SE", 0)

        if sample_records == 0:
            status = "connected_no_records"
            guidance.append(
                "JVOpen succeeded but no sample records were read. "
                "Confirm setup-data availability and fromtime."
            )
        elif ra_count == 0 and se_count == 0:
            status = "connected_no_ra_se"
            guidance.append(
                "JVOpen/JVGets connectivity is working, but the bounded "
                "sample contained no RA/SE. Continue to the larger RA/SE "
                "smoke export before treating this as a data problem."
            )
        else:
            status = "ready"
            guidance.append(
                "JV-Link connectivity is ready for the raw RA/SE export step."
            )

    except (JraVanApiError, JraVanUnavailableError, ValueError) as exc:
        message = str(exc)
        errors.append(message)
        code = _extract_code(message)
        hint = _guidance_for_code(code)
        if hint:
            guidance.append(hint)
        status = "blocked"
        sample_records = sum(counts.values())
        ra_count = counts.get("RA", 0)
        se_count = counts.get("SE", 0)
    except Exception as exc:
        errors.append(
            f"{type(exc).__name__}: {exc}"
        )
        guidance.append(
            "Unexpected JV-Link/COM failure. Confirm Python and JV-Link "
            "bitness match and run the official validation tool on this PC."
        )
        status = "blocked"
        sample_records = sum(counts.values())
        ra_count = counts.get("RA", 0)
        se_count = counts.get("SE", 0)
    finally:
        if client is not None:
            try:
                client.close()
            except Exception as exc:
                errors.append(f"JVClose failed: {exc}")
                status = "blocked"
        if own_client:
            client = None

    return JraVanDoctorReport(
        status=status,
        platform=platform.platform(),
        python_version=sys.version.split()[0],
        python_bits=struct.calcsize("P") * 8,
        sid=sid,
        from_time=from_time,
        option=option,
        initialized=initialized,
        status_before_open=status_before_open,
        open_return_code=open_code,
        read_count=read_count,
        download_count=download_count,
        last_file_timestamp=last_file_timestamp,
        sample_records=sample_records,
        record_type_counts=dict(sorted(counts.items())),
        ra_records=ra_count,
        se_records=se_count,
        errors=tuple(errors),
        guidance=tuple(guidance),
    )


def write_doctor_report(
    report: JraVanDoctorReport,
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
