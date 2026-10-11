"""Local-only JRA-VAN free-trial archive for pre-2025 research.

Raw JV-Data must remain on the self-hosted Windows PC. GitHub receives only a
sanitized manifest with counts, hashes and local paths.

The protected 2025-2026 final holdout remains unavailable to modeling. This
collector only uses a provider-bounded setup range ending inside provider year
2024 and intentionally excludes schedule/registration dataspecs (YSCH/TOKU)
that can describe future races.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable

from .jravan import JvLinkClient, JvOpenResult
from .phase11_jravan_bounded import (
    PHASE11_MIN_START,
    PHASE11_SAFE_SETUP_END,
    validate_phase11_jvopen_range,
)


# Setup-capable, research-useful dataspecs that do not intentionally describe
# future race schedules/registrations. Old+new IDs are retained because the
# 2023 schema migration split historical setup coverage across both families.
FREE_TRIAL_ARCHIVE_DATASPECS = (
    "RACE",
    "DIFF",
    "DIFN",
    "BLOD",
    "BLDN",
    "SNAP",
    "SNPN",
    "SLOP",
    "WOOD",
    "HOSE",
    "HOSN",
    "HOYU",
    "COMM",
    "MING",
)

DEFAULT_ARCHIVE_RANGE = (
    f"{PHASE11_MIN_START}-{PHASE11_SAFE_SETUP_END}"
)


@dataclass(frozen=True)
class ArchivePart:
    dataspec: str
    status: str
    records_written: int
    record_type_counts: dict[str, int]
    output_sha256: str | None
    output_path: str
    read_count: int | None
    download_count: int | None
    last_file_timestamp: str | None
    error: str | None


@dataclass(frozen=True)
class FreeTrialArchiveManifest:
    status: str
    created_at_utc: str
    jvopen_range: str
    option: int
    dataspecs: tuple[str, ...]
    excluded_dataspecs: tuple[str, ...]
    protected_holdout: str
    raw_redistribution_allowed: bool
    parts: tuple[ArchivePart, ...]
    total_records_written: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_one(
    *,
    dataspec: str,
    jvopen_range: str,
    archive_dir: Path,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
    progress_callback: Callable[[str], None] | None = None,
) -> ArchivePart:
    output = archive_dir / f"{dataspec.lower()}_raw.jsonl"
    staging = output.with_name(output.name + ".partial")
    output.parent.mkdir(parents=True, exist_ok=True)
    client = client_factory()
    counts: Counter[str] = Counter()
    written = 0
    open_result: JvOpenResult | None = None

    try:
        client.initialize()
        open_result = client.open_data(
            dataspec=dataspec,
            from_time=jvopen_range,
            option=4,
        )
        if progress_callback is not None:
            progress_callback(
                f"dataspec={dataspec} open read_count={open_result.read_count} "
                f"download_count={open_result.download_count}"
            )
        client.wait_for_downloads(
            open_result,
            progress_callback=progress_callback,
        )
        with staging.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            for record in client.iter_records():
                handle.write(
                    json.dumps(
                        asdict(record),
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                counts[record.record_type] += 1
                written += 1
                if (
                    progress_callback is not None
                    and written % 10000 == 0
                ):
                    progress_callback(
                        f"dataspec={dataspec} records={written}"
                    )

        # Do not replace an existing successful archive until a retry is complete.
        digest = _sha256(staging)
        staging.replace(output)
        return ArchivePart(
            dataspec=dataspec,
            status="success",
            records_written=written,
            record_type_counts=dict(sorted(counts.items())),
            output_sha256=digest,
            output_path=str(output),
            read_count=int(open_result.read_count),
            download_count=int(open_result.download_count),
            last_file_timestamp=str(
                open_result.last_file_timestamp
            ),
            error=None,
        )
    except Exception as exc:
        # A failed retry must never delete a previously successful archive.
        if staging.exists():
            staging.unlink()
        return ArchivePart(
            dataspec=dataspec,
            status="failed",
            records_written=0,
            record_type_counts={},
            output_sha256=None,
            output_path=str(output),
            read_count=(
                int(open_result.read_count)
                if open_result is not None
                else None
            ),
            download_count=(
                int(open_result.download_count)
                if open_result is not None
                else None
            ),
            last_file_timestamp=(
                str(open_result.last_file_timestamp)
                if open_result is not None
                else None
            ),
            error=f"{type(exc).__name__}: {exc}",
        )
    finally:
        client.close()


def archive_free_trial_pre2025(
    *,
    archive_dir: str | Path,
    manifest_path: str | Path,
    jvopen_range: str = DEFAULT_ARCHIVE_RANGE,
    dataspecs: tuple[str, ...] = FREE_TRIAL_ARCHIVE_DATASPECS,
    zero_cost_entitlement_confirmed: bool = False,
    personal_research_rights_confirmed: bool = False,
    client_factory: Callable[[], JvLinkClient] = JvLinkClient,
    progress_callback: Callable[[str], None] | None = None,
) -> FreeTrialArchiveManifest:
    start, end = validate_phase11_jvopen_range(
        jvopen_range
    )
    normalized_range = f"{start}-{end}"

    if zero_cost_entitlement_confirmed is not True:
        raise RuntimeError(
            "Free-trial archive requires explicit confirmation that the "
            "current local JV-Link entitlement is zero-cost."
        )
    if personal_research_rights_confirmed is not True:
        raise RuntimeError(
            "Free-trial archive requires explicit confirmation of personal "
            "research rights."
        )

    normalized_specs = tuple(
        str(value).strip().upper()
        for value in dataspecs
    )
    forbidden = {"YSCH", "TOKU"}
    if any(
        not value or not value.isalnum()
        for value in normalized_specs
    ):
        raise ValueError("archive dataspecs must be nonempty alphanumeric IDs")
    if forbidden.intersection(normalized_specs):
        raise ValueError(
            "YSCH/TOKU are excluded to avoid future race schedule/registration "
            "information crossing the protected holdout boundary."
        )

    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    parts: list[ArchivePart] = []
    for dataspec in normalized_specs:
        if progress_callback is not None:
            progress_callback(
                f"archive_start dataspec={dataspec}"
            )
        part = _export_one(
            dataspec=dataspec,
            jvopen_range=normalized_range,
            archive_dir=archive_dir,
            client_factory=client_factory,
            progress_callback=progress_callback,
        )
        parts.append(part)
        if progress_callback is not None:
            progress_callback(
                f"archive_complete dataspec={dataspec} "
                f"status={part.status} records={part.records_written}"
            )

    successes = [
        part for part in parts
        if part.status == "success"
    ]
    manifest = FreeTrialArchiveManifest(
        status=(
            "complete"
            if len(successes) == len(parts)
            else (
                "partial"
                if successes
                else "failed"
            )
        ),
        created_at_utc=datetime.now(
            timezone.utc
        ).isoformat(),
        jvopen_range=normalized_range,
        option=4,
        dataspecs=normalized_specs,
        excluded_dataspecs=("TOKU", "YSCH"),
        protected_holdout="2025-2026 not used for modeling/evaluation",
        raw_redistribution_allowed=False,
        parts=tuple(parts),
        total_records_written=sum(
            part.records_written
            for part in successes
        ),
    )

    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    manifest_path.write_text(
        json.dumps(
            asdict(manifest),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest
