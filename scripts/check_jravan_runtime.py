import struct
import sys


def main() -> None:
    print(
        f"Python={sys.version.split()[0]} "
        f"bits={struct.calcsize('P') * 8}"
    )

    try:
        import win32com.client.dynamic
    except ImportError as exc:
        raise SystemExit(
            "pywin32 is not installed in the JRA-VAN environment"
        ) from exc

    try:
        win32com.client.dynamic.Dispatch("JVDTLab.JVLink")
    except Exception as exc:
        raise SystemExit(
            "JV-Link COM is not registered or cannot be created: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    print("JV-Link COM=OK")


if __name__ == "__main__":
    main()
