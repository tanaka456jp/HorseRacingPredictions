"""Stage CURRENT-WEEK JRA-VAN RA/SE privately to a new PC2 D quarantine.

No full-history options, no protected-holdout training, no notebook upload,
no note, no overwrite. Local JV-Data remains subject to the user's Data Lab
licence and must NEVER be copied to GitHub or used for article publication.
This command only generates a private, append-once archive with a manifest.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import tempfile
from typing import Callable

from horse_racing_predictions.jravan import JvLinkClient
from horse_racing_predictions.jravan_parser import parse_ra, parse_se

PC2_NAME = "DESKTOP-MVV1FD4"
PC2_ROOT = Path("D:/HorseRacingPredictions/jravan-private-quarantine")
JST = timezone(timedelta(hours=9))
CAP = 20_000
MAX_PRIVATE_BYTES = 80_000_000
MIN_AVAILABLE_BYTES = 1_000_000_000


def _store_sanitized(report: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, sort_keys=True, ensure_ascii=False),
                    encoding="utf-8")


def quarantine_currentweek_ra_se(
    *, output: Path,
    client_factory: Callable[..., JvLinkClient] = JvLinkClient,
    root: Path = PC2_ROOT,
    computer: str | None = None,
    bits: int | None = None,
    windows: bool | None = None,
    quota_bytes: int | None = None,
) -> dict:
    if computer is None:
        computer = os.environ.get("COMPUTERNAME", "")
    if bits is None:
        bits = struct.calcsize("P") * 8
    if windows is None:
        windows = platform.system() == "Windows"
    report = {
        "schemaVersion": 1,
        "status": "BLOCKED",
        "stage": "NOT_STARTED",
        "verifiedPhysicalPC2": computer == PC2_NAME,
        "pythonBits": bits,
        "jvOpenAttempted": False,
        "jvOpenReturnCode": None,
        "jvCloseSucceeded": False,
        "recordCount": 0,
        "raCount": 0,
        "seCount": 0,
        "incompleteSnapshot": True,
        "maxRecords": CAP,
        "maxPrivateBytes": MAX_PRIVATE_BYTES,
        "freshDQuarantineOnly": True,
        "existingSnapshotsOverwritten": False,
        "savedLocally": False,
        "sourceRightsIndependentlyVerified": False,
        "protectedHoldoutTrainingAllowed": False,
        "notePostAttempted": False,
        "publicationAuthorized": False,
        "usageKeyRead": False,
        "rawDataUploaded": False,
    }
    if not (windows and computer == PC2_NAME and bits == 64):
        report["stage"] = "PHYSICAL_PC2_X64_REQUIRED"
        _store_sanitized(report, output)
        return report
    client = None
    snapshot: Path | None = None
    try:
        # Production does NOT allow a caller-controlled root; only tests
        # inject one. The CLI below deliberately exposes no --root argument.
        root = root.resolve(strict=False)
        if root.is_symlink():
            raise ValueError("UNTRUSTED_D_ROOT_LINK")
        if quota_bytes is None:
            parent = root if root.is_dir() else root.parent
            quota_bytes = shutil.disk_usage(parent).free
        if quota_bytes < MIN_AVAILABLE_BYTES:
            raise ValueError("INSUFFICIENT_D_SPACE")
        if root.exists() and not root.is_dir():
            raise ValueError("D_ARCHIVE_ROOT_NOT_DIRECTORY")
        root.mkdir(parents=True, exist_ok=True)
        snapshot = Path(tempfile.mkdtemp(
            prefix="RACE_CURRENTWEEK_QUARANTINE_",
            dir=str(root),
        ))
        marker = snapshot / "INCOMPLETE_DO_NOT_TRAIN"
        marker.write_text(
            "Private current-week JV-Data, 2025-2026 final holdout, "
            "never train/repost; incomplete until private manifest exists.",
            encoding="utf-8",
        )
        raw_path = snapshot / "race_raw.pending"
        report["stage"] = "COM_DISPATCH"
        _store_sanitized(report, output)
        client = client_factory(application_id="UNKNOWN")
        report["stage"] = "JVINIT"
        _store_sanitized(report, output)
        client.initialize()
        report["stage"] = "JVOPEN_CURRENT_WEEK_OPTION2"
        report["jvOpenAttempted"] = True
        _store_sanitized(report, output)
        opened = client.open_race(
            from_time="00000000000000", option=2,
        )
        report["jvOpenReturnCode"] = int(opened.return_code)
        client.wait_for_downloads(
            opened, max_polls=8, poll_seconds=0.5,
        )
        count: Counter[str] = Counter()
        total_bytes = 0
        report["stage"] = "SAVE_PRIVATE_RA_SE_ONLY"
        _store_sanitized(report, output)
        # Exclusive create. A partial file is NEVER a trainable dataset.
        with raw_path.open("x", encoding="utf-8", newline="\n") as handle:
            for record in client.iter_records(
                buffer_size=150_000, wait_retries=3, wait_seconds=0.1
            ):
                if record.record_type not in ("RA", "SE"):
                    continue
                # Ensure production parser accepts real RA/SE before storage.
                if record.record_type == "RA":
                    parse_ra(record.text)
                else:
                    parse_se(record.text)
                row = json.dumps(
                    {"record_type": record.record_type, "text": record.text},
                    ensure_ascii=False, separators=(",", ":"),
                ) + "\n"
                byte_length = len(row.encode("utf-8"))
                if total_bytes + byte_length > MAX_PRIVATE_BYTES:
                    raise ValueError("PRIVATE_QUARANTINE_SIZE_CAP")
                handle.write(row)
                total_bytes += byte_length
                count[record.record_type] += 1
                if sum(count.values()) >= CAP:
                    raise ValueError("CURRENT_WEEK_SNAPSHOT_TRUNCATED_AT_CAP")
        report["recordCount"] = sum(count.values())
        report["raCount"] = count["RA"]
        report["seCount"] = count["SE"]
        if not report["raCount"] or not report["seCount"]:
            report["stage"] = "RECORDS_NOT_COMPLETE_RA_SE"
            return report
        # Only close success can certify the private snapshot as complete.
        client.close()
        report["jvCloseSucceeded"] = True
        client = None
        digest = sha256(raw_path.read_bytes()).hexdigest()
        manifest = {
            "schemaVersion": 1,
            "source": "JVLINK_RACE_OPTION_2",
            "researchUseOnly": True,
            "status": "PRIVATE_JV_DATA_QUARANTINE",
            "collectionJstDay": datetime.now(JST).date().isoformat(),
            "recordCount": report["recordCount"],
            "raCount": report["raCount"],
            "seCount": report["seCount"],
            "recordSha256": digest,
            "trainOnThisFile": False,
            "protected2025And2026Holdout": True,
            "publicationAuthorized": False,
            "rawRedistributionAllowed": False,
            "sourceRightsIndependentlyVerified": False,
        }
        # Write manifest before renaming pending raw. Never replace old data.
        with (snapshot / "private_manifest.json").open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, sort_keys=True)
        raw_path.rename(snapshot / "race_raw.jsonl")
        report["status"] = "QUARANTINED_PRIVATE_RECORDS_NOT_TRAINABLE"
        report["stage"] = "COMPLETED_PRIVATE_QUARANTINE"
        report["savedLocally"] = True
        report["incompleteSnapshot"] = False
    except Exception:
        # No COM traceback, horse identities, file paths or licences in CI.
        report["status"] = "BLOCKED"
        if report["stage"] == "JVINIT":
            report["stage"] = "JVINIT_FAILED"
        elif report["stage"] == "JVOPEN_CURRENT_WEEK_OPTION2":
            report["stage"] = "CURRENT_WEEK_JVOPEN_FAILED"
        elif report["stage"] == "SAVE_PRIVATE_RA_SE_ONLY":
            report["stage"] = "PRIVATE_RECORD_PARSE_OR_CAP_FAILED"
        elif report["stage"] == "NOT_STARTED":
            report["stage"] = "D_QUARANTINE_PRECONDITION_FAILED"
        else:
            report["stage"] = "QUARANTINE_UNFINISHED"
    finally:
        if client is not None:
            try:
                client.close()
                report["jvCloseSucceeded"] = True
            except Exception:
                report["status"] = "BLOCKED"
                report["incompleteSnapshot"] = True
                report["savedLocally"] = False
        # Preserve all partial data with INCOMPLETE marker for forensic
        # inspection. NEVER delete, overwrite or move existing archives.
        _store_sanitized(report, output)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sanitized-output", type=Path, required=True)
    a = parser.parse_args()
    quarantine_currentweek_ra_se(output=a.sanitized_output)


if __name__ == "__main__":
    main()
