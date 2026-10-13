"""Verified migration of the private JRA-VAN archive from C: to D:."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil
from typing import Iterable

from .jravan_archive_paths import (
    default_archive_root,
    legacy_localappdata_archive_root,
)
from .jravan_archive_provenance import validate_local_pre2025_archive


@dataclass(frozen=True)
class ArchiveMigrationReport:
    status: str
    files_verified: int
    bytes_verified: int
    destination_manifest: str
    destination_manifest_sha256: str
    bldn_records_written: int
    bldn_sha256: str
    source_deleted_after_verify: bool
    source_tombstone_written: bool
    protected_holdout: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(16 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files(root: Path) -> dict[Path, Path]:
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }


def _existing_ancestor(path: Path) -> Path:
    current = path
    while not current.exists():
        parent = current.parent
        if parent == current:
            raise RuntimeError(
                f"no existing ancestor found for migration destination: {path}"
            )
        current = parent
    return current


def _rewrite_manifest_paths(
    manifest_path: Path,
    *,
    source_root: Path,
    destination_root: Path,
) -> None:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    parts = payload.get("parts")
    if isinstance(parts, list):
        for part in parts:
            if not isinstance(part, dict):
                continue
            value = str(part.get("output_path", "")).strip()
            if not value:
                continue
            old_path = Path(value)
            try:
                relative = old_path.relative_to(source_root)
            except ValueError:
                continue
            part["output_path"] = str(destination_root / relative)

    migration = dict(payload.get("migration") or {})
    migration.update({
        "migrated_from_legacy_localappdata": True,
        "destination_storage": "D-drive private archive",
        "raw_redistribution_allowed": False,
    })
    payload["migration"] = migration
    # Preserve both original manifests byte-for-byte as primary evidence.
    # Only a clearly named derived manifest may contain relocated paths.
    derived = manifest_path.parent / "relocated_manifest_v2.json"
    derived.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _rewrite_pedigree_report_path(
    report_path: Path,
    *,
    destination_root: Path,
) -> None:
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    manifest = destination_root / (
        "latest_manifest_v2.json"
        if (destination_root / "latest_manifest_v2.json").is_file()
        else "latest_manifest.json"
    )
    if "archive_manifest" in payload:
        payload["archive_manifest"] = str(manifest)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def migrate_archive_to_preferred_storage(
    *,
    source_root: str | Path | None = None,
    destination_root: str | Path | None = None,
    delete_source_after_verify: bool = False,
    min_free_margin_bytes: int = 1024 * 1024 * 1024,
) -> ArchiveMigrationReport:
    if delete_source_after_verify:
        raise RuntimeError(
            "Source deletion is disabled; separately approve C-drive cleanup "
            "after inspecting the verified migration and space-savings report."
        )

    source = Path(
        source_root
        if source_root is not None
        else legacy_localappdata_archive_root()
    )
    destination = Path(
        destination_root
        if destination_root is not None
        else default_archive_root()
    )

    if source.is_symlink() or destination.is_symlink():
        raise RuntimeError("archive migration roots must not be symlinks")

    source = source.resolve(strict=True)
    destination = destination.absolute()

    if source == destination:
        raise RuntimeError(
            "source and destination archive roots are identical; migration is unnecessary"
        )
    if destination.exists():
        raise RuntimeError(
            "destination archive root already exists; refusing to merge archives"
        )

    if any(path.is_symlink() for path in source.rglob("*")):
        raise RuntimeError("symlink found inside source archive; refusing migration")
    source_files = _files(source)
    if not source_files:
        raise RuntimeError("source JRA-VAN archive contains no files")

    source_bytes = sum(path.stat().st_size for path in source_files.values())
    existing_parent = _existing_ancestor(destination.parent)
    free_bytes = shutil.disk_usage(existing_parent).free
    required_bytes = source_bytes + max(
        int(min_free_margin_bytes),
        int(source_bytes * 0.05),
    )
    if free_bytes < required_bytes:
        raise RuntimeError(
            "destination drive does not have enough free space for a verified "
            f"archive migration: free={free_bytes}, required={required_bytes}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".migrating")
    if staging.exists():
        raise RuntimeError(
            f"staging migration directory already exists: {staging}"
        )

    try:
        shutil.copytree(
            source,
            staging,
            copy_function=shutil.copy2,
        )

        staged_files = _files(staging)
        if set(staged_files) != set(source_files):
            raise RuntimeError(
                "destination staging file inventory differs from source"
            )

        verified_bytes = 0
        file_checksums: list[dict[str, str | int]] = []
        for relative in sorted(source_files, key=lambda value: str(value)):
            left = source_files[relative]
            right = staged_files[relative]
            if left.stat().st_size != right.stat().st_size:
                raise RuntimeError(
                    f"file size mismatch during migration: {relative}"
                )
            source_hash = _sha256(left)
            if source_hash != _sha256(right):
                raise RuntimeError(
                    f"SHA-256 mismatch during migration: {relative}"
                )
            verified_bytes += left.stat().st_size
            file_checksums.append({
                "relative_path": relative.as_posix(),
                "size_bytes": int(left.stat().st_size),
                "sha256": source_hash,
            })

        # Local private verification inventory, never included in GitHub Artifacts.
        (staging / "migration_file_hashes.json").write_text(
            json.dumps(file_checksums, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for manifest_name in (
            "latest_manifest.json",
            "latest_manifest_v2.json",
        ):
            manifest = staging / manifest_name
            if manifest.is_file():
                _rewrite_manifest_paths(
                    manifest,
                    source_root=source,
                    destination_root=destination,
                )

        # Keep the copied pedigree report immutable, just like source manifests.

        staging.rename(destination)

        provenance = validate_local_pre2025_archive(
            destination,
            required_dataspecs=("BLDN",),
        )
        bldn = provenance.parts[0]

        snapshot = destination / "pedigree_snapshot.csv"
        snapshot_report = destination / "pedigree_snapshot_report.json"
        if snapshot.is_file() and snapshot_report.is_file():
            payload = json.loads(
                snapshot_report.read_text(encoding="utf-8")
            )
            expected = str(payload.get("snapshot_sha256", "")).strip().lower()
            if expected and _sha256(snapshot) != expected:
                raise RuntimeError(
                    "migrated pedigree snapshot SHA-256 does not match its report"
                )

        manifest_hash = _sha256(provenance.manifest_path)
        report = ArchiveMigrationReport(
            status="verified",
            files_verified=len(source_files),
            bytes_verified=int(verified_bytes),
            destination_manifest=provenance.manifest_path.name,
            destination_manifest_sha256=manifest_hash,
            bldn_records_written=int(bldn.records_written),
            bldn_sha256=bldn.sha256,
            source_deleted_after_verify=False,
            source_tombstone_written=False,
            protected_holdout="2025-2026 untouched",
        )

        receipt_path = destination / "migration_receipt.json"
        receipt_path.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return report
    except Exception:
        # If the final destination already exists, preserve it for diagnosis.
        # Only incomplete staging is safe to remove automatically.
        if staging.exists():
            shutil.rmtree(staging)
        raise
