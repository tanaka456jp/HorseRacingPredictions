"""Parse JRA-VAN SK progeny-master records into pedigree linkage keys.

The parser follows JVData 4.9.0.1 record 19 (SK, 208 bytes). Raw breeding
registration identifiers are linkage keys only; downstream models must not
consume them as categorical or numeric features.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable

import pandas as pd


SK_RECORD_BYTES = 208
PEDIGREE_SLOT_COUNT = 14
PEDIGREE_SLOT_BYTES = 10

PEDIGREE_ORDER = (
    "sire",
    "dam",
    "sire_sire",
    "sire_dam",
    "dam_sire",
    "dam_dam",
    "sire_sire_sire",
    "sire_sire_dam",
    "sire_dam_sire",
    "sire_dam_dam",
    "dam_sire_sire",
    "dam_sire_dam",
    "dam_dam_sire",
    "dam_dam_dam",
)


@dataclass(frozen=True)
class SkPedigreeRecord:
    data_division: str
    created_date: str
    blood_registration_number: str
    birth_date: str
    sire_breeding_registration_number: str
    dam_breeding_registration_number: str
    damsire_breeding_registration_number: str
    pedigree_registration_numbers: tuple[str, ...]


def _raw_bytes(text: str) -> bytes:
    try:
        return text.encode("cp932")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "SK record could not be round-tripped to CP932"
        ) from exc


def _ascii(raw: bytes, position: int, length: int) -> str:
    start = position - 1
    end = start + length
    if len(raw) < end:
        raise ValueError(
            f"record too short for position={position}, length={length}"
        )
    return raw[start:end].decode(
        "ascii",
        errors="replace",
    ).strip()


def parse_sk(text: str) -> SkPedigreeRecord:
    raw = _raw_bytes(text)
    if len(raw) < SK_RECORD_BYTES - 2:
        raise ValueError(
            "SK record must contain at least 206 data bytes before CR/LF"
        )
    if _ascii(raw, 1, 2) != "SK":
        raise ValueError("not an SK record")

    blood = _ascii(raw, 12, 10)
    if not blood:
        raise ValueError("SK blood registration number is empty")

    pedigree = tuple(
        _ascii(
            raw,
            67 + index * PEDIGREE_SLOT_BYTES,
            PEDIGREE_SLOT_BYTES,
        )
        for index in range(PEDIGREE_SLOT_COUNT)
    )

    return SkPedigreeRecord(
        data_division=_ascii(raw, 3, 1),
        created_date=_ascii(raw, 4, 8),
        blood_registration_number=blood,
        birth_date=_ascii(raw, 22, 8),
        sire_breeding_registration_number=pedigree[0],
        dam_breeding_registration_number=pedigree[1],
        damsire_breeding_registration_number=pedigree[4],
        pedigree_registration_numbers=pedigree,
    )


def select_latest_sk(
    records: Iterable[SkPedigreeRecord],
) -> dict[str, SkPedigreeRecord]:
    """Keep latest SK update per blood registration number.

    Data-division 0 is a deletion and removes the key. For equal created dates,
    later input order wins so a local JV stream can be replayed deterministically.
    """
    latest: dict[str, SkPedigreeRecord] = {}
    latest_key: dict[str, tuple[str, int]] = {}

    for order, record in enumerate(records):
        blood = record.blood_registration_number
        key = (record.created_date, order)
        if key < latest_key.get(blood, ("", -1)):
            continue
        latest_key[blood] = key
        if record.data_division == "0":
            latest.pop(blood, None)
        else:
            latest[blood] = record
    return latest


def load_sk_pedigree_jsonl(
    path: str | Path,
) -> pd.DataFrame:
    """Load only SK records from a local JV raw JSONL archive."""
    parsed: list[SkPedigreeRecord] = []
    path = Path(path)

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
                if str(payload.get("record_type", "")).upper() != "SK":
                    continue
                parsed.append(parse_sk(str(payload["text"])))
            except Exception as exc:
                raise ValueError(
                    f"invalid SK JSONL line {line_number}: {exc}"
                ) from exc

    latest = select_latest_sk(parsed)
    rows = []
    for blood, record in sorted(latest.items()):
        rows.append({
            "blood_registration_number": blood,
            "sire_breeding_registration_number": (
                record.sire_breeding_registration_number
            ),
            "dam_breeding_registration_number": (
                record.dam_breeding_registration_number
            ),
            "damsire_breeding_registration_number": (
                record.damsire_breeding_registration_number
            ),
            "pedigree_created_date": record.created_date,
        })

    return pd.DataFrame(
        rows,
        columns=[
            "blood_registration_number",
            "sire_breeding_registration_number",
            "dam_breeding_registration_number",
            "damsire_breeding_registration_number",
            "pedigree_created_date",
        ],
    )
