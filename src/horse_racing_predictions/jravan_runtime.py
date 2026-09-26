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
    python_bits = struct.calcsize("P") * 8
    registered_64bit, registered_32bit = _probe_registry_views()
    guidance = list(
        classify_registration(
            registered_64bit=registered_64bit,
            registered_32bit=registered_32bit,
            python_bits=python_bits,
        )
    )

    if sys.platform != "win32":
        return JraVanRuntimeReport(
            status="unsupported_platform",
            python_version=sys.version.split()[0],
            python_bits=python_bits,
            progid=PROGID,
            registered_64bit=registered_64bit,
            registered_32bit=registered_32bit,
            com_created=False,
            error="JV-Link COM requires Windows.",
            guidance=tuple(guidance),
        )

    try:
        import win32com.client.dynamic
    except ImportError as exc:
        return JraVanRuntimeReport(
            status="blocked",
            python_version=sys.version.split()[0],
            python_bits=python_bits,
            progid=PROGID,
            registered_64bit=registered_64bit,
            registered_32bit=registered_32bit,
            com_created=False,
            error=f"pywin32 is not installed: {exc}",
            guidance=tuple(guidance),
        )

    try:
        win32com.client.dynamic.Dispatch(PROGID)
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        hresult = getattr(exc, "hresult", None)
        if (
            hresult == INVALID_CLASS_STRING_HRESULT
            or "2147221005" in message
        ):
            guidance.insert(
                0,
                "COM returned 0x800401F3 (Invalid class string): the ProgID "
                "is not registered in the Python process COM view."
            )
        return JraVanRuntimeReport(
            status="blocked",
            python_version=sys.version.split()[0],
            python_bits=python_bits,
            progid=PROGID,
            registered_64bit=registered_64bit,
            registered_32bit=registered_32bit,
            com_created=False,
            error=message,
            guidance=tuple(guidance),
        )

    return JraVanRuntimeReport(
        status="ready",
        python_version=sys.version.split()[0],
        python_bits=python_bits,
        progid=PROGID,
        registered_64bit=registered_64bit,
        registered_32bit=registered_32bit,
        com_created=True,
        error=None,
        guidance=tuple(guidance),
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
