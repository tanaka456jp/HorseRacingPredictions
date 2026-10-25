"""Future Sunday local AI input audit, always non-publishing and fail-closed.

Checks a user-provided, locally approved snapshot; no network, JV-Link, key
read, model training, holdout read, note API, or publishing. A local manifest
is NOT independent JRA/source-rights evidence. Live launch still requires
separately signed source, model, outsider, and authenticated note proof.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import re
from typing import Any

from .data_sources import read_csv_flexible
from .model_artifact import load_champion_artifact
from .sunday_ai_research import private_sunday_ai_preview
from .sunday_auto_post_readiness import _as_local

JST = timezone(timedelta(hours=9))
COURSES = frozenset({
    "SAPPORO", "HAKODATE", "FUKUSHIMA", "NIIGATA", "NAKAYAMA",
    "TOKYO", "CHUKYO", "KYOTO", "HANSHIN", "KOKURA",
})
INPUTS = (
    ("MODEL", "model/manifest.json"),
    ("MODEL", "model/model.cbm"),
    ("HISTORY", "race_history.csv"),
    ("ENTRIES", "sunday_entries.csv"),
    ("RACE_MANIFEST", "race_manifest.json"),
)
DUAL_INPUTS = (
    ("MODEL", "model/candidate_manifest.json"),
    ("MODEL", "model/win.cbm"),
    ("MODEL", "model/outsider.cbm"),
    ("HISTORY", "race_history.csv"),
    ("ENTRIES", "sunday_entries.csv"),
    ("RACE_MANIFEST", "race_manifest.json"),
)
SHA = re.compile(r"[0-9a-f]{64}\Z")


def _strict_date(value: str) -> date:
    if type(value) is not str:
        raise ValueError("ISO race date required")
    target = date.fromisoformat(value)
    if target.isoformat() != value or target.weekday() != 6:
        raise ValueError("target must be a canonical Sunday")
    return target


def _parse_local_manifest(root: Path, race_date: str) -> tuple[str, ...]:
    path = _as_local(root, "race_manifest.json", max_bytes=200_000)

    def no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, val in pairs:
            if key in obj:
                raise ValueError("duplicate manifest key")
            obj[key] = val
        return obj

    doc = json.loads(
        path.read_text(encoding="utf-8"), object_pairs_hook=no_duplicates,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
    )
    if (not isinstance(doc, dict)
            or doc.get("raceDate") != race_date
            or doc.get("sourceKind") != "jra-official-pre-race-card"):
        raise ValueError("wrong race date or source manifest type")
    ids = doc.get("expectedRaceIds")
    if (not isinstance(ids, list)
            or len(ids) not in (12, 24, 36)
            or not all(type(value) is str for value in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("incomplete, duplicate or invalid JRA race IDs")
    pattern = re.compile(
        r"JRA-" + race_date.replace("-", "") +
        r"-([A-Z]+)-(0[1-9]|1[0-2])\Z"
    )
    courses: dict[str, set[int]] = {}
    for rid in ids:
        m = pattern.fullmatch(rid)
        if m is None or m.group(1) not in COURSES:
            raise ValueError("race ID venue/date/number not canonical")
        courses.setdefault(m.group(1), set()).add(int(m.group(2)))
    if (len(courses) != len(ids) // 12
            or any(nums != set(range(1, 13)) for nums in courses.values())):
        raise ValueError("full twelve-race card required per named venue")
    # This is only a *self-declared* card. No release approval is inferred.
    return tuple(ids)


def diagnose_future_sunday_bundle(
    root: Path, *, race_date: str, observed_at: datetime,
    model_mode: str = "single",
) -> dict[str, Any]:
    """Inspect a reviewed existing local candidate; never authorize posting."""
    day = _strict_date(race_date)
    if (not isinstance(observed_at, datetime)
            or observed_at.utcoffset() is None):
        raise ValueError("timezone-aware observation timestamp required")
    if not isinstance(root, Path):
        raise ValueError("root must be a Path")
    if model_mode not in ("single", "dual"):
        raise ValueError("model mode must be single or dual")
    input_roles = DUAL_INPUTS if model_mode == "dual" else INPUTS

    def blocked(reasons: list[str], **extra: Any) -> dict[str, Any]:
        return {
            "schemaVersion": 1, "raceDate": race_date,
            "status": "BLOCKED", "blockers": reasons,
            "modelComputed": False, "publicationAuthorized": False,
            "sourceRightsIndependentlyVerified": False,
            "modelTrainingProvenanceIndependentlyVerified": False,
            "independentOutsiderModelVerified": False,
            "notePostAttempted": False, "providerAccessAttempted": False,
            "usageKeyRead": False, "protectedHoldoutOpened": False,
            "rawDataUploaded": False, **extra,
        }

    now_jst = observed_at.astimezone(JST)
    allowed_date = day - timedelta(days=2) <= now_jst.date() < day
    early_race_day = (now_jst.date() == day
                      and now_jst.time() < time(8, 0))
    if not (allowed_date or early_race_day):
        if now_jst.date() < day - timedelta(days=2):
            # Filename presence only. Never open private CSV/model bytes before
            # the authorized forecast window, even when assets exist.
            exists = not root.is_symlink() and root.is_dir()
            missing = sorted(set(
                role for role, relative in input_roles
                if not exists or (root / relative).is_symlink()
                or not (root / relative).is_file()
            ))
            return blocked(
                ["PRE_RACE_WINDOW_NOT_YET_OPEN"],
                localCandidateBundlePresent=exists,
                missingInputRoles=missing,
            )
        return blocked(["PRE_RACE_WINDOW_EXPIRED"])
    if root.is_symlink() or not root.is_dir():
        return blocked(["LOCAL_BUNDLE_MISSING"])
    missing = sorted(set(
        role for role, relative in input_roles
        if not (root / relative).is_file()
        or (root / relative).is_symlink()
    ))
    if missing:
        return blocked(["LOCAL_INPUTS_INCOMPLETE"], missingInputRoles=missing)

    try:
        ids = _parse_local_manifest(root, race_date)
        if model_mode == "dual":
            for path in ("model/candidate_manifest.json", "model/win.cbm",
                         "model/outsider.cbm"):
                _as_local(root, path, max_bytes=400_000_000)
        else:
            _as_local(root, "model/model.cbm", max_bytes=400_000_000)
            _as_local(root, "model/manifest.json", max_bytes=200_000)
        history = read_csv_flexible(
            _as_local(root, "race_history.csv", max_bytes=400_000_000)
        )
        entrants = read_csv_flexible(
            _as_local(root, "sunday_entries.csv", max_bytes=60_000_000)
        )
        if model_mode == "dual":
            from .dual_candidate_private_preview import (
                load_dual_research_candidate, private_dual_sunday_preview,
            )
            candidate = load_dual_research_candidate(root / "model")
            preview = private_dual_sunday_preview(
                candidate, history=history, entries=entrants,
                race_date=race_date, expected_race_ids=ids,
                observed_at=observed_at,
            )
            model_hash = preview.get("winModelOutputSha256")
            outsider_hash = preview.get("outsiderSelectionSha256")
            if (preview.get("bothActualModelsExecuted") is not True
                    or not SHA.fullmatch(str(outsider_hash))):
                raise ValueError("both native model inferences not verified")
        else:
            champion = load_champion_artifact(root / "model")
            preview = private_sunday_ai_preview(
                champion=champion, history=history, entries=entrants,
                race_date=race_date, expected_race_ids=ids,
                observed_at=observed_at,
            )
            model_hash = preview.get("modelOutputSha256")
        if (preview.get("raceCount") != len(ids)
                or preview.get("runnerCount") != len(entrants)
                or not SHA.fullmatch(str(model_hash))):
            raise ValueError("incomplete model output")
        report = blocked([
            "INDEPENDENT_SOURCE_RIGHTS_NOT_VERIFIED",
            "INDEPENDENT_TRAINING_PROVENANCE_NOT_VERIFIED",
            "INDEPENDENT_OUTSIDER_MODEL_NOT_VERIFIED",
            "SIGNED_NOTE_PUBLICATION_GATE_MISSING",
        ])
        report["modelComputed"] = True
        report["raceCount"] = len(ids)
        report["runnerCount"] = len(entrants)
        report["modelOutputSha256"] = model_hash
        if model_mode == "dual":
            report["bothActualModelsExecuted"] = True
            report["outsiderSelectionSha256"] = outsider_hash
            report["independentOutsiderModelVerified"] = False
        return report
    except (OSError, TypeError, ValueError, KeyError, RuntimeError,
            UnicodeError, json.JSONDecodeError, ImportError):
        return blocked(["REAL_LOCAL_MODEL_INFERENCE_NOT_VERIFIED"])
