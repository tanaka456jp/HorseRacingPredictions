"""Read-only one-shot readiness for the Oct 25, 2026 JRA Sunday forecast.

Consumes ONLY existing local inputs. No data download, JRA-VAN/JV-Link calls,
account access, note publication, protected-holdout training, betting, or
license purchases. Files and raw horse data never appear in the report.

A real computed Top 3 remains a *private* candidate pending independent
training/source verification and a separately frozen outsider model.
"""
from __future__ import annotations

from datetime import date, datetime, time, timezone, timedelta
from hashlib import sha256
import json
from pathlib import Path
import re

from .data_sources import read_csv_flexible
from .model_artifact import load_champion_artifact
from .sunday_ai_research import private_sunday_ai_preview

_JST = timezone(timedelta(hours=9))
_DAY = "2026-10-25"
_MAX_DATA = 400 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED = frozenset({
    "model/manifest.json", "model/model.cbm",
    "race_history.csv", "sunday_entries.csv", "race_manifest.json",
})


def _as_local(root: Path, path: str, *, max_bytes: int) -> Path:
    target = root / path
    if not target.is_file() or target.is_symlink():
        raise ValueError("missing or linked candidate")
    if target.stat().st_size == 0 or target.stat().st_size > max_bytes:
        raise ValueError("missing, empty or oversized candidate")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("candidate escapes local root")
    return target


def _read_manifest(root: Path) -> tuple[str, ...]:
    manifest = _as_local(root, "race_manifest.json", max_bytes=250_000)
    raw = manifest.read_bytes()
    def unique_keys(pairs):
        value = {}
        for k, v in pairs:
            if k in value:
                raise ValueError("duplicate JSON key")
            value[k] = v
        return value
    doc = json.loads(raw, object_pairs_hook=unique_keys,
                     parse_constant=lambda _x: (_ for _ in ()).throw(ValueError("nonfinite")))
    ids = doc.get("expectedRaceIds") if isinstance(doc, dict) else None
    if not (isinstance(doc, dict) and doc.get("raceDate") == _DAY
            and doc.get("sourceKind") == "jra-official-pre-race-card"
            and isinstance(ids, list) and len(ids) == 36
            and len(ids) == len(set(ids))
            and all(type(x) is str and re.fullmatch(
                r"JRA-20261025-(?:TOKYO|KYOTO|NIIGATA)-(?:0?[1-9]|1[0-2])",
                x
            ) for x in ids)):
        raise ValueError("not a complete official JRA Sunday 36-race candidate")
    for course in ("TOKYO", "KYOTO", "NIIGATA"):
        selected = {int(x.rsplit("-", 1)[1]) for x in ids if x.startswith(
            "JRA-20261025-" + course + "-"
        )}
        if selected != set(range(1, 13)):
            raise ValueError("12 race IDs per scheduled JRA venue required")
    return tuple(ids)


def diagnose_sunday_auto_post(
    root: Path, *, observed_at: datetime,
) -> dict:
    """Validate runnable candidate without ever granting publication."""
    if not isinstance(observed_at, datetime) or observed_at.utcoffset() is None:
        raise ValueError("timezone-aware inspection timestamp required")
    if not isinstance(root, Path):
        raise ValueError("local root must be Path")
    # This historic one-day run is impossible to certify as a pre-race
    # forecast after the research cutoff, even if local data later appears.
    # Check time BEFORE attempting to inspect a local model or snapshot.
    now_jst = observed_at.astimezone(_JST)
    if now_jst.date() > date(2026, 10, 25) or (
        now_jst.date() == date(2026, 10, 25)
        and now_jst.time() >= time(8, 0)
    ):
        return {
            "status": "BLOCKED", "raceDate": _DAY,
            "blockers": ["HISTORIC_PRE_RACE_CUTOFF_EXPIRED"],
            "modelComputed": False, "publicationAuthorized": False,
            "notePostAttempted": False, "providerAccessAttempted": False,
            "rawDataUploaded": False,
        }
    if root.is_symlink() or not root.is_dir():
        return {
            "status": "BLOCKED", "raceDate": _DAY,
            "blockers": ["LOCAL_BUNDLE_MISSING"],
            "publicationAuthorized": False,
            "notePostAttempted": False,
            "providerAccessAttempted": False,
            "rawDataUploaded": False,
        }
    missing = sorted(
        name for name in _REQUIRED
        if not (root / name).is_file() or (root / name).is_symlink()
    )
    if missing:
        return {
            "status": "BLOCKED", "raceDate": _DAY,
            "blockers": ["LOCAL_INPUTS_INCOMPLETE"],
            "missingInputRoles": [
                "MODEL" if x.startswith("model/") else (
                    "RACE_MANIFEST" if "manifest" in x else (
                        "HISTORY" if "history" in x else "ENTRIES"))
                for x in missing
            ],
            "publicationAuthorized": False,
            "notePostAttempted": False,
            "providerAccessAttempted": False,
            "rawDataUploaded": False,
        }
    report = {
        "status": "BLOCKED", "raceDate": _DAY,
        "blockers": [], "modelComputed": False,
        "publicationAuthorized": False, "notePostAttempted": False,
        "providerAccessAttempted": False, "rawDataUploaded": False,
    }
    try:
        ids = _read_manifest(root)
        _as_local(root, "model/model.cbm", max_bytes=_MAX_DATA)
        _as_local(root, "model/manifest.json", max_bytes=250_000)
        history_path = _as_local(root, "race_history.csv", max_bytes=_MAX_DATA)
        entries_path = _as_local(root, "sunday_entries.csv", max_bytes=60_000_000)
        champion = load_champion_artifact(root / "model")
        history = read_csv_flexible(history_path)
        entries = read_csv_flexible(entries_path)
        preview = private_sunday_ai_preview(
            champion=champion, history=history, entries=entries,
            expected_race_ids=ids, race_date=_DAY, observed_at=observed_at,
        )
        if preview["raceCount"] != 36 or not _SHA.fullmatch(
            preview["modelOutputSha256"]
        ):
            raise ValueError("runtime model proof incomplete")
        report["modelComputed"] = True
        report["modelOutputSha256"] = preview["modelOutputSha256"]
        report["raceCount"] = preview["raceCount"]
        report["runnerCount"] = preview["runnerCount"]
    except (OSError, ValueError, TypeError, KeyError, RuntimeError,
            UnicodeError, json.JSONDecodeError):
        report["blockers"].append("REAL_SUNDAY_MODEL_INFERENCE_NOT_VERIFIED")
    # No self-attested file, metadata SHA, or model name is allowed to
    # authorize a note post. This pipeline intentionally cannot sign the
    # independent source-rights/horse/outsider/model verification receipts.
    report["blockers"].extend([
        "INDEPENDENT_SOURCE_RIGHTS_NOT_VERIFIED",
        "INDEPENDENT_MODEL_PROVENANCE_NOT_VERIFIED",
        "INDEPENDENT_OUTSIDER_MODEL_NOT_VERIFIED",
        "INDEPENDENT_PUBLICATION_RECEIPT_NOT_VERIFIED",
        "SUNDAY_AUTHENTICATED_NOTE_POST_AND_MAGAZINE_PROOF_MISSING",
    ])
    return report
