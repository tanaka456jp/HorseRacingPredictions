"""Resolve the private local JRA-VAN archive location.

Raw provider data never belongs in the repository. On Windows, prefer the D:
drive when it exists so large free-trial archives do not consume the system
drive. An explicit environment variable always wins.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping


ARCHIVE_ROOT_ENV = "HORSE_RACING_JRAVAN_ARCHIVE_ROOT"
D_DRIVE_ARCHIVE_ROOT = Path(
    r"D:\HorseRacingPredictions\JraVanFreeTrialArchive\pre2025"
)


def legacy_localappdata_archive_root(
    env: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if env is None else env
    local = values.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError(
            "LOCALAPPDATA is required when no explicit JRA-VAN archive "
            "root is configured."
        )
    return (
        Path(local)
        / "HorseRacingPredictions"
        / "JraVanFreeTrialArchive"
        / "pre2025"
    )


def default_archive_root(
    env: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if env is None else env
    override = str(values.get(ARCHIVE_ROOT_ENV, "")).strip()
    if override:
        return Path(override)

    # Keep this check deliberately simple and local. On non-Windows CI the
    # drive root does not exist, so tests naturally fall back to LOCALAPPDATA.
    d_root = Path(r"D:\")
    if d_root.exists():
        return D_DRIVE_ARCHIVE_ROOT

    return legacy_localappdata_archive_root(values)
