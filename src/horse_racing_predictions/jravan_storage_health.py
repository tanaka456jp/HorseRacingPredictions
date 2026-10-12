"""Sanitized storage health for the private JRA-VAN archive."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from .jravan_archive_paths import (
    D_DRIVE_ARCHIVE_ROOT,
    default_archive_root,
    legacy_localappdata_archive_root,
)


GIB = 1024 ** 3
DEFAULT_MIN_D_FREE_BYTES = 10 * GIB
DEFAULT_C_WARN_FREE_BYTES = 15 * GIB


@dataclass(frozen=True)
class JraVanStorageHealth:
    status: str
    archive_root: str
    archive_on_d_drive: bool
    d_drive_available: bool
    d_total_bytes: int | None
    d_free_bytes: int | None
    d_free_gib: float | None
    d_min_free_bytes: int
    d_space_ready: bool
    c_total_bytes: int | None
    c_free_bytes: int | None
    c_free_gib: float | None
    c_warn_free_bytes: int
    c_space_warning: bool
    legacy_c_archive_exists: bool
    legacy_c_tombstone_exists: bool
    raw_provider_files_on_legacy_c: int
    protected_holdout: str
    raw_records_read: bool


def _disk_usage(path: Path):
    existing = path
    while not existing.exists():
        parent = existing.parent
        if parent == existing:
            return None
        existing = parent
    return shutil.disk_usage(existing)


def _is_on_drive(path: Path, drive: str) -> bool:
    return path.drive.upper() == drive.upper()


def inspect_jravan_storage_health(
    *,
    min_d_free_bytes: int = DEFAULT_MIN_D_FREE_BYTES,
    c_warn_free_bytes: int = DEFAULT_C_WARN_FREE_BYTES,
) -> JraVanStorageHealth:
    if min_d_free_bytes < 0 or c_warn_free_bytes < 0:
        raise ValueError("storage thresholds must be non-negative")

    root = default_archive_root()
    d_drive = Path("D:\\")
    d_available = d_drive.exists()
    d_usage = _disk_usage(d_drive) if d_available else None

    c_drive = Path("C:\\")
    c_usage = _disk_usage(c_drive) if c_drive.exists() else None

    legacy = legacy_localappdata_archive_root()
    tombstone = legacy / "MOVED_TO_D.json"
    raw_names = (
        "race_raw.jsonl",
        "blod_raw.jsonl",
        "bldn_raw.jsonl",
        "snap_raw.jsonl",
        "snpn_raw.jsonl",
        "slop_raw.jsonl",
        "wood_raw.jsonl",
        "ming_raw.jsonl",
    )
    raw_on_c = sum(
        1
        for name in raw_names
        if (legacy / name).is_file()
    )

    d_free = int(d_usage.free) if d_usage is not None else None
    c_free = int(c_usage.free) if c_usage is not None else None
    archive_on_d = _is_on_drive(root, "D:")
    d_ready = bool(
        d_available
        and archive_on_d
        and d_free is not None
        and d_free >= int(min_d_free_bytes)
    )
    c_warning = bool(
        c_free is not None
        and c_free < int(c_warn_free_bytes)
    )

    violations = []
    if d_available and not archive_on_d:
        violations.append("archive_root_not_on_d")
    if d_available and not d_ready:
        violations.append("d_free_space_below_minimum")
    if raw_on_c:
        violations.append("legacy_c_raw_provider_files_present")

    return JraVanStorageHealth(
        status="ready" if not violations else "blocked",
        archive_root=str(root),
        archive_on_d_drive=archive_on_d,
        d_drive_available=d_available,
        d_total_bytes=(int(d_usage.total) if d_usage is not None else None),
        d_free_bytes=d_free,
        d_free_gib=(round(d_free / GIB, 2) if d_free is not None else None),
        d_min_free_bytes=int(min_d_free_bytes),
        d_space_ready=d_ready,
        c_total_bytes=(int(c_usage.total) if c_usage is not None else None),
        c_free_bytes=c_free,
        c_free_gib=(round(c_free / GIB, 2) if c_free is not None else None),
        c_warn_free_bytes=int(c_warn_free_bytes),
        c_space_warning=c_warning,
        legacy_c_archive_exists=legacy.exists(),
        legacy_c_tombstone_exists=tombstone.is_file(),
        raw_provider_files_on_legacy_c=raw_on_c,
        protected_holdout="2025-2026 untouched",
        raw_records_read=False,
    )


def assert_jravan_archive_storage_ready(
    *,
    min_d_free_bytes: int = DEFAULT_MIN_D_FREE_BYTES,
) -> JraVanStorageHealth:
    health = inspect_jravan_storage_health(
        min_d_free_bytes=min_d_free_bytes,
    )
    if not health.d_drive_available:
        raise RuntimeError(
            "D drive is unavailable; refuse large JRA-VAN archive acquisition "
            "on the system drive."
        )
    if not health.archive_on_d_drive:
        raise RuntimeError(
            "JRA-VAN archive root is not on D drive."
        )
    if not health.d_space_ready:
        raise RuntimeError(
            "D drive does not have the minimum free-space margin for JRA-VAN "
            f"archive acquisition: free={health.d_free_bytes}, "
            f"required={health.d_min_free_bytes}"
        )
    if health.raw_provider_files_on_legacy_c:
        raise RuntimeError(
            "Legacy C-drive raw JRA-VAN files are present; refuse acquisition "
            "until storage routing is reconciled."
        )
    return health
