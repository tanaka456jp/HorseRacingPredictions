from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import struct
import sys
from pathlib import Path


PROGID = "JVDTLab.JVLink"
INVALID_CLASS_STRING_HRESULT = -2147221005


@dataclass(frozen=True)
class JraVanRuntimeReport:
    status: str
    python_version: str
    python_bits: int
    progid: str
    registered_64bit: bool | None
    registered_32bit: bool | None
    com_created: bool
    error: str | None
    guidance: tuple[str, ...]


def classify_registration(
    *,
    registered_64bit: bool | None,
    registered_32bit: bool | None,
    python_bits: int,
) -> tuple[str, ...]:
    guidance: list[str] = []

    if python_bits == 64:
        if registered_64bit is False and registered_32bit is True:
            guidance.append(
                "32-bit JV-Link is registered, but 64-bit JV-Link is not. "
                "Install the official JV-Link 64-bit edition before retrying."
            )
        elif registered_64bit is False and registered_32bit is False:
            guidance.append(
                "JV-Link is not registered in either 32-bit or 64-bit COM. "
                "Install JV-Link and retry."
            )
        elif registered_64bit is True:
            guidance.append(
                "64-bit JV-Link registration exists. If COM creation still "
                "fails, repair/reinstall JV-Link 64-bit."
            )
    elif python_bits == 32:
        if registered_32bit is False and registered_64bit is True:
            guidance.append(
                "64-bit JV-Link is registered, but this Python is 32-bit. "
                "Use 64-bit Python or install JV-Link 32-bit."
            )
        elif registered_32bit is False and registered_64bit is False:
            guidance.append(
                "JV-Link is not registered in either COM view."
            )

    return tuple(guidance)


def _probe_registry_views() -> tuple[bool | None, bool | None]:
    if sys.platform != "win32":
        return None, None

    import winreg

    def exists(flag: int) -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT,
                PROGID,
                0,
                winreg.KEY_READ | flag,
            )
        except FileNotFoundError:
            return False
        else:
            winreg.CloseKey(key)
            return True

    return (
        exists(winreg.KEY_WOW64_64KEY),
        exists(winreg.KEY_WOW64_32KEY),
    )


def inspect_jravan_runtime() -> JraVanRuntimeReport:
    # The free Data Lab trial has expired. Even COM *construction* can open
    # an authentication/expiry browser page. Never Dispatch JV-Link during
    # runtime checks; only offline code and fictional tests may proceed.
    return JraVanRuntimeReport(
        status="disabled_trial_expired",
        python_version=sys.version.split()[0],
        python_bits=struct.calcsize("P") * 8,
        progid=PROGID,
        registered_64bit=None,
        registered_32bit=None,
        com_created=False,
        error="JRA_VAN_TRIAL_EXPIRED_LIVE_COM_DISABLED",
        guidance=(
            "All new JRA-VAN/JV-Link connections are disabled.",
            "Use approved non-JRA-VAN offline research instead.",
        ),
    )


def write_runtime_report(
    report: JraVanRuntimeReport,
    path: str | Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path
