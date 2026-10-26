"""PC2 x64-only JV-Link RACE option2 bounded in-memory record-type smoke.

Raw JV-Data must never be printed, written, shared, or used as the 2025/26
protected final evaluation set. This is a private technical diagnostic:
max 12 records, current-week option2 only, no historical option3/4 setup,
no Kaggle, no note, no secrets. Caller enforces a child-process watchdog.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import platform
import re
import struct
from typing import Callable

from horse_racing_predictions.jravan import JvLinkClient

_VALID_TYPE = re.compile(r"[A-Z0-9]{2}\Z")
MAX_RECORDS = 12
MAX_DIAGNOSTIC_RECORDS = 8192


@dataclass
class BoundedJvReadReport:
    schemaVersion: int = 1
    status: str = "BLOCKED"
    stage: str = "NOT_STARTED"
    verifiedPhysicalPC2: bool = False
    selectedPythonBits: int = 0
    dataSpec: str = "RACE"
    option: int = 2
    noHistoricalSetup: bool = True
    jvInitSucceeded: bool = False
    jvOpenAttempted: bool = False
    jvOpenReturnCode: int | None = None
    downloadCount: int | None = None
    jvRecordReadAttempted: bool = False
    maxRecords: int = MAX_RECORDS
    sampleRecordCount: int = 0
    recordTypeCounts: dict[str, int] | None = None
    jvCloseSucceeded: bool = False
    summaryMetadataOnly: bool = True
    rawRecordsSaved: bool = False
    rawRecordsUploaded: bool = False
    protectedHoldoutTrainingAttempted: bool = False
    usageKeyRead: bool = False
    notePostAttempted: bool = False
    publicationAuthorized: bool = False


def _store(report: BoundedJvReadReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(asdict(report), ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )


def probe_bounded_race_types(
    *, output: Path,
    client_factory: Callable[..., JvLinkClient] = JvLinkClient,
    computer: str | None = None, bits: int | None = None,
    max_records: int = MAX_RECORDS,
    windows: bool | None = None,
) -> dict:
    if type(max_records) is not int or max_records not in (12, 256, 1024, 8192):
        raise ValueError("bounded read permits only 12, 256, 1024, or 8192 records")
    if computer is None:
        computer = os.environ.get("COMPUTERNAME", "")
    if bits is None:
        bits = struct.calcsize("P") * 8
    if windows is None:
        windows = platform.system() == "Windows"
    report = BoundedJvReadReport(
        verifiedPhysicalPC2=computer == "DESKTOP-MVV1FD4",
        selectedPythonBits=bits, recordTypeCounts={},
        maxRecords=max_records,
    )
    if not (windows and computer == "DESKTOP-MVV1FD4" and bits == 64):
        report.stage = "PC2_WINDOWS_X64_REQUIRED"
        _store(report, output)
        return asdict(report)
    client = None
    counts: Counter[str] = Counter()
    try:
        report.stage = "COM_DISPATCH"
        _store(report, output)
        client = client_factory(application_id="UNKNOWN")
        report.stage = "JVINIT"
        _store(report, output)
        client.initialize()
        report.jvInitSucceeded = True
        report.stage = "JVOPEN_CURRENT_WEEK"
        report.jvOpenAttempted = True
        _store(report, output)
        result = client.open_race(from_time="00000000000000", option=2)
        report.jvOpenReturnCode = int(result.return_code)
        report.downloadCount = int(result.download_count)
        if report.jvOpenReturnCode < 0:
            raise RuntimeError("RACE_OPEN_NEGATIVE")
        # Current-week JVOpen may not itself download any file (rc 0 is
        # successful). If downloads are pending, bound wait to <= 4 sec.
        report.stage = "WAIT_LIMITED_DOWNLOAD"
        _store(report, output)
        client.wait_for_downloads(
            result, max_polls=8, poll_seconds=0.5,
        )
        report.stage = "RECORD_TYPE_SAMPLE"
        report.jvRecordReadAttempted = True
        _store(report, output)
        for raw in client.iter_records(
            buffer_size=150_000, wait_retries=3, wait_seconds=0.1
        ):
            # Only record TYPE is retained; even filenames, offsets, sample
            # text, jockeys and horse IDs are discarded immediately.
            type_id = str(raw.record_type)
            if not _VALID_TYPE.fullmatch(type_id):
                type_id = "OTHER"
            counts[type_id] += 1
            if sum(counts.values()) >= max_records:
                break
            # Once both essential schema types are seen after the original
            # 12-record smoke, stop; do not examine more private JV-Data.
            if (max_records > MAX_RECORDS
                    and counts["RA"] > 0 and counts["SE"] > 0):
                break
        report.sampleRecordCount = sum(counts.values())
        report.recordTypeCounts = dict(sorted(counts.items()))
        report.status = "SAMPLE_METADATA_ONLY"
        report.stage = (
            "CURRENT_WEEK_SAMPLE_READ"
            if report.sampleRecordCount else "CURRENT_WEEK_NO_RECORDS"
        )
    except Exception:
        # Never leak COM exception or raw records in logs.
        report.status = "BLOCKED"
        if report.stage == "RECORD_TYPE_SAMPLE":
            report.stage = "JVGETS_OR_RECORD_STREAM_FAILED"
        elif report.stage == "WAIT_LIMITED_DOWNLOAD":
            report.stage = "CURRENT_WEEK_DOWNLOAD_WAIT_FAILED"
        elif report.stage == "JVOPEN_CURRENT_WEEK":
            report.stage = "JVOPEN_AUTH_FAILED_OR_COM_ERROR"
        elif report.stage == "JVINIT":
            report.stage = "JVINIT_FAILED_OR_COM_ERROR"
        else:
            report.stage = "COM_DISPATCH_FAILED"
    finally:
        if client is not None:
            try:
                client.close()
                report.jvCloseSucceeded = True
            except Exception:
                report.stage = "JVCLOSE_FAILED"
                report.status = "BLOCKED"
        if report.status == "SAMPLE_METADATA_ONLY" and not report.jvCloseSucceeded:
            report.status = "BLOCKED"
        _store(report, output)
    return asdict(report)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-records", type=int, choices=(12, 256, 1024, 8192), default=12,
    )
    args = parser.parse_args()
    probe_bounded_race_types(output=args.output, max_records=args.max_records)


if __name__ == "__main__":
    main()
