"""Pure local interpreter metadata for PC2 runner; never imports COM.

Prints only interpreter word size and pywin32 package availability.
No paths, licence keys, personal environment, provider or data access.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys

def inspect() -> dict[str, int | bool]:
    try:
        installed = importlib.util.find_spec("win32com") is not None
    except (ImportError, ValueError, AttributeError):
        installed = False
    return {"bits": struct.calcsize("P") * 8, "pywin32": installed, "pythonMajor": sys.version_info.major, "pythonMinor": sys.version_info.minor}

if __name__ == "__main__":
    print(json.dumps(inspect(), sort_keys=True))
