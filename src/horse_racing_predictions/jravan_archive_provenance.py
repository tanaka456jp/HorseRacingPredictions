"""Validate local JRA-VAN free-trial archive provenance before research use."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

from .jravan_free_trial_archive import DEFAULT_ARCHIVE_RANGE


@dataclass(frozen=True)
class ValidatedArchivePart:
    dataspec: str
    path: Path
    records_written: int
    sha256: str


@dataclass(frozen=True)
class ValidatedArchiveProvenance:
    archive_root: Path
    manifest_path: Path
    jvopen_range: str
    protected_holdout: str
    manifest_status: str
    parts: tuple[ValidatedArchivePart, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def validate_local_pre2025_archive(
    archive_root: str | Path,
    *,
    required_dataspecs: Iterable[str] = ("RACE",),
    manifest_name: str = "latest_manifest.json",
) -> ValidatedArchiveProvenance:
    """Fail closed unless required local files match the bounded archive manifest."""
    root_input = Path(archive_root)
    if root_input.is_symlink():
        raise RuntimeError(
            "JRA-VAN archive root must not be a symlink."
        )
    root = root_input.resolve(strict=True)

    manifest_input = root / manifest_name
    if manifest_input.is_symlink():
        raise RuntimeError(
            "JRA-VAN archive manifest must not be a symlink."
        )
    manifest_path = manifest_input.resolve(strict=True)
    if not _inside(root, manifest_path):
        raise RuntimeError(
            "JRA-VAN archive manifest resolves outside the local archive root."
        )
    payload = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )
    if payload.get("jvopen_range") != DEFAULT_ARCHIVE_RANGE:
        raise RuntimeError(
            "JRA-VAN archive range differs from the approved pre-2025 "
            f"provider bound {DEFAULT_ARCHIVE_RANGE}."
        )
    if payload.get("raw_redistribution_allowed") is not False:
        raise RuntimeError(
            "JRA-VAN archive manifest does not explicitly forbid raw redistribution."
        )
    protected = str(
        payload.get("protected_holdout", "")
    )
    if "2025-2026" not in protected:
        raise RuntimeError(
            "JRA-VAN archive manifest does not preserve the 2025-2026 holdout."
        )

    status = str(payload.get("status", ""))
    if status not in {"complete", "partial"}:
        raise RuntimeError(
            f"JRA-VAN archive manifest status is not usable: {status!r}"
        )

    requested = tuple(
        str(value).strip().upper()
        for value in required_dataspecs
    )
    if not requested or any(not value for value in requested):
        raise ValueError(
            "required_dataspecs must contain at least one nonempty dataspec"
        )
    if len(set(requested)) != len(requested):
        raise ValueError(
            "required_dataspecs contains duplicates"
        )

    raw_parts = payload.get("parts")
    if not isinstance(raw_parts, list):
        raise RuntimeError(
            "JRA-VAN archive manifest parts must be a list."
        )

    by_dataspec: dict[str, dict] = {}
    for part in raw_parts:
        if not isinstance(part, dict):
            raise RuntimeError(
                "JRA-VAN archive manifest contains an invalid part entry."
            )
        dataspec = str(
            part.get("dataspec", "")
        ).strip().upper()
        if not dataspec:
            raise RuntimeError(
                "JRA-VAN archive manifest part has no dataspec."
            )
        if dataspec in by_dataspec:
            raise RuntimeError(
                f"duplicate JRA-VAN archive manifest part: {dataspec}"
            )
        by_dataspec[dataspec] = part

    validated: list[ValidatedArchivePart] = []
    for dataspec in requested:
        part = by_dataspec.get(dataspec)
        if part is None:
            raise RuntimeError(
                f"required JRA-VAN archive dataspec is missing: {dataspec}"
            )
        if part.get("status") != "success":
            raise RuntimeError(
                f"required JRA-VAN archive dataspec is not successful: {dataspec}"
            )

        expected_hash = str(
            part.get("output_sha256", "")
        ).strip().lower()
        if len(expected_hash) != 64 or any(
            char not in "0123456789abcdef"
            for char in expected_hash
        ):
            raise RuntimeError(
                f"invalid SHA-256 in JRA-VAN archive manifest for {dataspec}"
            )

        raw_path_text = str(
            part.get("output_path", "")
        ).strip()
        if not raw_path_text:
            raise RuntimeError(
                f"archive manifest path is empty for {dataspec}"
            )
        raw_path = Path(raw_path_text)
        if not raw_path.is_absolute():
            raw_path = root / raw_path
        if raw_path.is_symlink():
            raise RuntimeError(
                f"archive file for {dataspec} must not be a symlink"
            )
        raw_path = raw_path.resolve(strict=True)
        if not _inside(root, raw_path):
            raise RuntimeError(
                f"archive file for {dataspec} resolves outside local archive root"
            )
        if not raw_path.is_file():
            raise RuntimeError(
                f"archive file for {dataspec} is not a regular file"
            )

        actual_hash = _sha256(raw_path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"archive SHA-256 mismatch for {dataspec}"
            )

        records_written = int(
            part.get("records_written", 0)
        )
        if records_written <= 0:
            raise RuntimeError(
                f"archive record count must be positive for {dataspec}"
            )

        validated.append(
            ValidatedArchivePart(
                dataspec=dataspec,
                path=raw_path,
                records_written=records_written,
                sha256=actual_hash,
            )
        )

    return ValidatedArchiveProvenance(
        archive_root=root,
        manifest_path=manifest_path,
        jvopen_range=DEFAULT_ARCHIVE_RANGE,
        protected_holdout=protected,
        manifest_status=status,
        parts=tuple(validated),
    )
