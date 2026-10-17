import json

import pytest

from horse_racing_predictions.jravan_pedigree import (
    PEDIGREE_ORDER,
    load_sk_pedigree_jsonl,
    parse_sk,
    select_latest_sk,
)


def _put(raw: bytearray, position: int, length: int, value: str) -> None:
    encoded = value.encode("ascii")
    if len(encoded) > length:
        raise ValueError(value)
    start = position - 1
    raw[start:start + length] = encoded.ljust(length, b" ")


def sk_text(
    *,
    division: str = "1",
    created: str = "20240101",
    blood: str = "2020A00001",
    sire: str = "SIRE000001",
    dam: str = "DAM0000001",
    damsire: str = "DMSIRE0001",
) -> str:
    raw = bytearray(b" " * 206)
    _put(raw, 1, 2, "SK")
    _put(raw, 3, 1, division)
    _put(raw, 4, 8, created)
    _put(raw, 12, 10, blood)
    _put(raw, 22, 8, "20200315")
    _put(raw, 30, 1, "1")
    _put(raw, 31, 1, "1")
    _put(raw, 32, 2, "01")
    _put(raw, 34, 1, "0")
    _put(raw, 35, 4, "0000")
    _put(raw, 39, 8, "00000001")

    pedigree = [
        sire,
        dam,
        "SSIRE00001",
        "SDAM000001",
        damsire,
        "DMDAM00001",
        "SSSIRE0001",
        "SSDAM00001",
        "SDSIRE0001",
        "SDDAM00001",
        "DSSIRE0001",
        "DSDAM00001",
        "DDSIRE0001",
        "DDDAM00001",
    ]
    for index, value in enumerate(pedigree):
        _put(raw, 67 + index * 10, 10, value)

    return raw.decode("ascii")


def test_parse_sk_uses_official_three_generation_slot_order():
    record = parse_sk(sk_text())

    assert record.blood_registration_number == "2020A00001"
    assert record.sire_breeding_registration_number == "SIRE000001"
    assert record.dam_breeding_registration_number == "DAM0000001"
    assert record.damsire_breeding_registration_number == "DMSIRE0001"
    assert len(record.pedigree_registration_numbers) == 14
    assert PEDIGREE_ORDER[0] == "sire"
    assert PEDIGREE_ORDER[1] == "dam"
    assert PEDIGREE_ORDER[4] == "dam_sire"
    assert record.pedigree_registration_numbers[4] == "DMSIRE0001"


def test_parse_sk_rejects_wrong_type_or_short_record():
    with pytest.raises(ValueError, match="not an SK"):
        parse_sk("HN" + " " * 204)
    with pytest.raises(ValueError, match="at least 206"):
        parse_sk("SK" + " " * 100)


def test_latest_sk_update_wins_and_delete_removes_key():
    first = parse_sk(
        sk_text(created="20240101", sire="SIRE000001")
    )
    updated = parse_sk(
        sk_text(
            created="20240201",
            division="2",
            sire="SIRE000002",
        )
    )
    latest = select_latest_sk([first, updated])
    assert (
        latest["2020A00001"].sire_breeding_registration_number
        == "SIRE000002"
    )

    deleted = parse_sk(
        sk_text(
            created="20240301",
            division="0",
            sire="SIRE000002",
        )
    )
    assert select_latest_sk([first, updated, deleted]) == {}


def test_load_sk_jsonl_ignores_non_sk_and_exports_only_linkage_columns(tmp_path):
    path = tmp_path / "bldn_raw.jsonl"
    rows = [
        {"record_type": "HN", "text": "HN" + " " * 248},
        {"record_type": "SK", "text": sk_text()},
    ]
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    frame = load_sk_pedigree_jsonl(path)

    assert list(frame.columns) == [
        "blood_registration_number",
        "sire_breeding_registration_number",
        "dam_breeding_registration_number",
        "damsire_breeding_registration_number",
        "pedigree_created_date",
    ]
    assert len(frame) == 1
    assert frame.loc[0, "sire_breeding_registration_number"] == "SIRE000001"
