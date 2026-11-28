"""Prepare an explicit 72-month NAR research manifest from one chosen folder.

No source bytes are opened: only names and filesystem type are inspected.
The operator must choose a dedicated folder containing *only* the licensed
2017-01 .. 2022-12 NAR monthly race ZIPs, not JRA-VAN archives or the
2023-24 independent/2025-26 protected holdouts.

The returned exact path list is PRIVATE and intentionally hidden from repr.
It is never uploaded or logged. Network and model calls are absent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .nar_official_zip_probe import UnsafeNarSource, _ZIP_RE

_REQUIRED_MONTHS = frozenset(
    f"{year}{month:02d}" for year in range(2017, 2023)
    for month in range(1, 13)
)
_BLOCKED_SEGMENTS = frozenset({
    "jra-van", "jravan-private-quarantine",
    "holdout", "final-evaluation", "2025-2026-holdout",
})


@dataclass(frozen=True)
class NarPrivateMonthlyManifest:
    status: str
    observed_months: int
    required_months: int
    missing_months: tuple[str, ...]
    absolute_source_paths: tuple[Path, ...] = field(repr=False)
    contains_newly_downloaded_data: bool = False
    opened_zip_bytes: bool = False
    model_training_approved: bool = False
    source_rights_verified_by_software: bool = False


def inventory_private_nar_training_directory(
    folder: Path, *, personal_private_permission_confirmed: bool,
) -> NarPrivateMonthlyManifest:
    """Read only a manually selected directory's immediate filenames."""
    if personal_private_permission_confirmed is not True:
        raise UnsafeNarSource("NAR_MANIFEST_PERSONAL_PERMISSION_REQUIRED")
    if (not isinstance(folder, Path) or not folder.is_absolute()
            or folder.is_symlink()
            or any(parent.is_symlink() for parent in folder.parents)
            or not folder.is_dir()
            or any(piece.casefold() in _BLOCKED_SEGMENTS
                   for piece in folder.parts)):
        raise UnsafeNarSource("NAR_MANIFEST_UNTRUSTED_DIRECTORY")
    month_paths: dict[str, Path] = {}
    for path in folder.iterdir():
        if path.is_symlink():
            raise UnsafeNarSource("NAR_MANIFEST_SYMLINK_FORBIDDEN")
        if path.is_dir():
            raise UnsafeNarSource("NAR_MANIFEST_RECURSION_FORBIDDEN")
        if not path.is_file():
            raise UnsafeNarSource("NAR_MANIFEST_NONREGULAR_ENTRY")
        if path.suffix.lower() != ".zip":
            # An operator may keep license and ZIP receipt texts in this
            # folder, but no other ZIP archives may be silently ignored.
            continue
        match = _ZIP_RE.fullmatch(path.name)
        if match is None or match.group(1) not in _REQUIRED_MONTHS:
            raise UnsafeNarSource("NAR_MANIFEST_UNEXPECTED_OR_SEALED_ZIP")
        month = match.group(1)
        if month in month_paths:
            raise UnsafeNarSource("NAR_MANIFEST_DUPLICATE_MONTH")
        month_paths[month] = path
    missing = tuple(sorted(_REQUIRED_MONTHS - set(month_paths)))
    ordered = tuple(month_paths[m] for m in sorted(month_paths))
    return NarPrivateMonthlyManifest(
        status=("NAR_PRIVATE_72_MONTH_FILENAMES_READY_BYTES_UNREAD"
                if not missing
                else "NAR_PRIVATE_MONTHS_MISSING_BYTES_UNREAD"),
        observed_months=len(ordered),
        required_months=len(_REQUIRED_MONTHS),
        missing_months=missing,
        absolute_source_paths=ordered,
    )
