from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

import pandas as pd


JV_DATA_SPEC_VERSION = "4.9.0.1"

CENTRAL_RACECOURSES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}

WEATHER = {
    "0": "UNKNOWN",
    "1": "晴",
    "2": "曇",
    "3": "雨",
    "4": "小雨",
    "5": "雪",
    "6": "小雪",
}

TRACK_CONDITION = {
    "0": "UNKNOWN",
    "1": "良",
    "2": "稍重",
    "3": "重",
    "4": "不良",
}

SEX = {
    "0": "UNKNOWN",
    "1": "牡",
    "2": "牝",
    "3": "セ",
}

GRADE = {
    "A": "G1",
    "B": "G2",
    "C": "G3",
    "D": "重賞",
    "E": "特別",
    "F": "J-G1",
    "G": "J-G2",
    "H": "J-G3",
    "L": "L",
    "": "NONE",
    " ": "NONE",
}

RACE_CLASS = {
    "000": "UNKNOWN",
    "001": "100万円以下",
    "002": "200万円以下",
    "003": "300万円以下",
    "005": "1勝クラス",
    "010": "2勝クラス",
    "016": "3勝クラス",
    "099": "9900万円以下",
    "100": "1億円以下",
    "701": "新馬",
    "702": "未出走",
    "703": "未勝利",
    "999": "オープン",
}

DATA_PRIORITY = {
    "0": 0,
    "1": 10,
    "2": 20,
    "3": 30,
    "4": 40,
    "5": 50,
    "6": 60,
    "7": 70,
    "9": 5,
    "A": 70,
    "B": 70,
}


@dataclass(frozen=True)
class RaceRecord:
    race_id: str
    data_division: str
    race_date: str
    racecourse_code: str
    racecourse: str
    meet_number: str
    meet_day: str
    race_number: str
    grade_code: str
    graded_race: str
    race_class_code: str
    race_class: str
    distance_m: int | None
    track_code: str
    surface: str
    weather_code: str
    weather: str
    turf_condition_code: str
    dirt_condition_code: str
    track_condition: str


@dataclass(frozen=True)
class HorseRaceRecord:
    race_id: str
    data_division: str
    post_position: int | None
    blood_registration_number: str
    horse_name: str
    sex_code: str
    sex: str
    age: int | None
    trainer: str
    carried_weight: float | None
    jockey: str
    horse_weight: int | None
    horse_weight_delta: int | None
    abnormal_code: str
    finish_position: int | None
    corner_1: int | None
    corner_2: int | None
    corner_3: int | None
    corner_4: int | None
    win_odds: float | None
    popularity: int | None
    last_3f: float | None


@dataclass(frozen=True)
class JraVanParseReport:
    spec_version: str
    raw_records: int
    ra_records_seen: int
    se_records_seen: int
    selected_ra_records: int
    selected_se_records: int
    output_rows: int
    output_races: int
    skipped_non_jra_ra: int
    skipped_non_jra_se: int
    skipped_incomplete_se: int
    unmatched_se: int
    warnings: tuple[str, ...]


def _raw_bytes(text: str) -> bytes:
    try:
        return text.encode("cp932")
    except UnicodeEncodeError as exc:
        raise ValueError(
            "JV-Data record could not be round-tripped to CP932"
        ) from exc


def _slice(raw: bytes, position: int, length: int) -> bytes:
    start = position - 1
    end = start + length
    if len(raw) < end:
        raise ValueError(
            f"record is too short for position={position}, length={length}: "
            f"{len(raw)} bytes"
        )
    return raw[start:end]


def _ascii(raw: bytes, position: int, length: int) -> str:
    return _slice(raw, position, length).decode(
        "ascii",
        errors="replace",
    ).strip()


def _text(raw: bytes, position: int, length: int) -> str:
    return _slice(raw, position, length).decode(
        "cp932",
        errors="replace",
    ).strip().strip("\u3000")


def _int_value(
    raw: bytes,
    position: int,
    length: int,
    *,
    zero_is_none: bool = False,
) -> int | None:
    value = _ascii(raw, position, length)
    if not value or not value.isdigit():
        return None
    number = int(value)
    if zero_is_none and number == 0:
        return None
    return number


def _race_id(raw: bytes) -> tuple[str, str, str, str, str, str]:
    year = _ascii(raw, 12, 4)
    mmdd = _ascii(raw, 16, 4)
    course = _ascii(raw, 20, 2)
    meet = _ascii(raw, 22, 2)
    day = _ascii(raw, 24, 2)
    race = _ascii(raw, 26, 2)
    if not (
        len(year) == 4
        and len(mmdd) == 4
        and course
        and meet
        and day
        and race
    ):
        raise ValueError("invalid JV-Data race key")
    key = f"{year}{mmdd}-{course}-{meet}-{day}-{race}"
    return key, year, mmdd, course, meet, day


def _surface(track_code: str) -> str:
    try:
        value = int(track_code)
    except (TypeError, ValueError):
        return "UNKNOWN"
    if 10 <= value <= 22:
        return "芝"
    if 23 <= value <= 29:
        return "ダート"
    if 51 <= value <= 59:
        return "障害"
    return "UNKNOWN"


def _condition_code(raw: bytes) -> str:
    candidates = [
        _ascii(raw, 635, 3),
        _ascii(raw, 623, 3),
        _ascii(raw, 626, 3),
        _ascii(raw, 629, 3),
        _ascii(raw, 632, 3),
    ]
    for value in candidates:
        if value and value != "000":
            return value
    return "000"


def parse_ra(text: str) -> RaceRecord:
    raw = _raw_bytes(text)
    if _ascii(raw, 1, 2) != "RA":
        raise ValueError("not an RA record")
    if len(raw) < 1270:
        raise ValueError(
            f"RA record must contain at least 1270 data bytes, got {len(raw)}"
        )

    race_id, year, mmdd, course, meet, day = _race_id(raw)
    race_number = _ascii(raw, 26, 2)
    grade_code = _ascii(raw, 615, 1)
    class_code = _condition_code(raw)
    track_code = _ascii(raw, 706, 2)
    surface = _surface(track_code)
    turf_condition = _ascii(raw, 889, 1)
    dirt_condition = _ascii(raw, 890, 1)
    if surface == "ダート":
        chosen_condition = dirt_condition
    else:
        chosen_condition = turf_condition

    return RaceRecord(
        race_id=race_id,
        data_division=_ascii(raw, 3, 1),
        race_date=f"{year}-{mmdd[:2]}-{mmdd[2:]}",
        racecourse_code=course,
        racecourse=CENTRAL_RACECOURSES.get(
            course,
            f"COURSE_{course}",
        ),
        meet_number=meet,
        meet_day=day,
        race_number=race_number,
        grade_code=grade_code,
        graded_race=GRADE.get(
            grade_code,
            f"GRADE_{grade_code}" if grade_code else "NONE",
        ),
        race_class_code=class_code,
        race_class=RACE_CLASS.get(
            class_code,
            f"CLASS_{class_code}",
        ),
        distance_m=_int_value(raw, 698, 4),
        track_code=track_code,
        surface=surface,
        weather_code=_ascii(raw, 888, 1),
        weather=WEATHER.get(
            _ascii(raw, 888, 1),
            "UNKNOWN",
        ),
        turf_condition_code=turf_condition,
        dirt_condition_code=dirt_condition,
        track_condition=TRACK_CONDITION.get(
            chosen_condition,
            "UNKNOWN",
        ),
    )


def _weight_delta(raw: bytes) -> int | None:
    sign = _ascii(raw, 328, 1)
    magnitude_text = _ascii(raw, 329, 3)
    if not magnitude_text or not magnitude_text.isdigit():
        return None
    magnitude = int(magnitude_text)
    if magnitude == 999:
        return None
    if sign == "-":
        return -magnitude
    if sign == "+":
        return magnitude
    if magnitude == 0:
        return 0
    return None


def _horse_weight(raw: bytes) -> int | None:
    value = _int_value(raw, 325, 3)
    if value in (None, 0, 999):
        return None
    return value


def _decimal_tenth(
    raw: bytes,
    position: int,
    length: int,
    *,
    sentinel: int | None = None,
) -> float | None:
    value = _int_value(raw, position, length)
    if value is None:
        return None
    if sentinel is not None and value == sentinel:
        return None
    return value / 10.0


def parse_se(text: str) -> HorseRaceRecord:
    raw = _raw_bytes(text)
    if _ascii(raw, 1, 2) != "SE":
        raise ValueError("not an SE record")
    if len(raw) < 553:
        raise ValueError(
            f"SE record must contain at least 553 data bytes, got {len(raw)}"
        )

    race_id, _year, _mmdd, _course, _meet, _day = _race_id(raw)
    sex_code = _ascii(raw, 79, 1)

    finish_position = _int_value(
        raw,
        335,
        2,
        zero_is_none=True,
    )
    win_odds = _decimal_tenth(
        raw,
        360,
        4,
    )
    if win_odds is not None and win_odds <= 0:
        win_odds = None

    return HorseRaceRecord(
        race_id=race_id,
        data_division=_ascii(raw, 3, 1),
        post_position=_int_value(
            raw,
            29,
            2,
            zero_is_none=True,
        ),
        blood_registration_number=_ascii(
            raw,
            31,
            10,
        ),
        horse_name=_text(raw, 41, 36),
        sex_code=sex_code,
        sex=SEX.get(sex_code, "UNKNOWN"),
        age=_int_value(
            raw,
            83,
            2,
            zero_is_none=True,
        ),
        trainer=_text(raw, 91, 8),
        carried_weight=_decimal_tenth(
            raw,
            289,
            3,
        ),
        jockey=_text(raw, 307, 8),
        horse_weight=_horse_weight(raw),
        horse_weight_delta=_weight_delta(raw),
        abnormal_code=_ascii(raw, 332, 1),
        finish_position=finish_position,
        corner_1=_int_value(
            raw,
            352,
            2,
            zero_is_none=True,
        ),
        corner_2=_int_value(
            raw,
            354,
            2,
            zero_is_none=True,
        ),
        corner_3=_int_value(
            raw,
            356,
            2,
            zero_is_none=True,
        ),
        corner_4=_int_value(
            raw,
            358,
            2,
            zero_is_none=True,
        ),
        win_odds=win_odds,
        popularity=_int_value(
            raw,
            364,
            2,
            zero_is_none=True,
        ),
        last_3f=_decimal_tenth(
            raw,
            391,
            3,
            sentinel=999,
        ),
    )


def _priority(data_division: str) -> int:
    return DATA_PRIORITY.get(data_division, -1)


def _select_latest(
    current,
    candidate,
):
    if current is None:
        return candidate
    if _priority(candidate.data_division) >= _priority(
        current.data_division
    ):
        return candidate
    return current


def parse_raw_jsonl(
    path: str | Path,
    *,
    jra_only: bool = True,
    completed_only: bool = True,
) -> tuple[pd.DataFrame, JraVanParseReport]:
    path = Path(path)
    races: dict[str, RaceRecord] = {}
    horses: dict[tuple[str, str], HorseRaceRecord] = {}

    raw_records = 0
    ra_seen = 0
    se_seen = 0
    skipped_non_jra_ra = 0
    skipped_non_jra_se = 0
    warnings: list[str] = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            raw_records += 1
            try:
                payload = json.loads(line)
                record_type = str(
                    payload.get("record_type", "")
                )
                text = str(payload["text"])

                if record_type == "RA":
                    ra_seen += 1
                    record = parse_ra(text)
                    if (
                        jra_only
                        and record.racecourse_code
                        not in CENTRAL_RACECOURSES
                    ):
                        skipped_non_jra_ra += 1
                        continue
                    races[record.race_id] = _select_latest(
                        races.get(record.race_id),
                        record,
                    )
                elif record_type == "SE":
                    se_seen += 1
                    raw = _raw_bytes(text)
                    course = _ascii(raw, 20, 2)
                    if (
                        jra_only
                        and course not in CENTRAL_RACECOURSES
                    ):
                        skipped_non_jra_se += 1
                        continue
                    record = parse_se(text)
                    horse_key = (
                        record.race_id,
                        record.blood_registration_number
                        or str(record.post_position)
                        or record.horse_name,
                    )
                    horses[horse_key] = _select_latest(
                        horses.get(horse_key),
                        record,
                    )
            except Exception as exc:
                raise ValueError(
                    f"invalid JV-Data JSONL line {line_number}: {exc}"
                ) from exc

    rows = []
    skipped_incomplete_se = 0
    unmatched_se = 0

    for horse in horses.values():
        race = races.get(horse.race_id)
        if race is None:
            unmatched_se += 1
            continue

        if completed_only and (
            horse.finish_position is None
            or horse.win_odds is None
            or horse.win_odds <= 1.0
        ):
            skipped_incomplete_se += 1
            continue

        rows.append({
            "race_id": race.race_id,
            "race_date": race.race_date,
            "racecourse": race.racecourse,
            "surface": race.surface,
            "distance_m": race.distance_m,
            "weather": race.weather,
            "track_condition": race.track_condition,
            "finish_position": horse.finish_position,
            "post_position": horse.post_position,
            "horse_name": horse.horse_name,
            "sex": horse.sex,
            "age": horse.age,
            "carried_weight": horse.carried_weight,
            "jockey": horse.jockey,
            "win_odds": horse.win_odds,
            "horse_weight": horse.horse_weight,
            "horse_weight_delta": horse.horse_weight_delta,
            "trainer": horse.trainer,
            "last_3f": horse.last_3f,
            "corner_1": horse.corner_1,
            "corner_2": horse.corner_2,
            "corner_3": horse.corner_3,
            "corner_4": horse.corner_4,
            "race_class": race.race_class,
            "graded_race": race.graded_race,
            "_jv_data_division_ra": race.data_division,
            "_jv_data_division_se": horse.data_division,
            "_jv_course_code": race.racecourse_code,
            "_jv_track_code": race.track_code,
            "_jv_grade_code": race.grade_code,
            "_jv_race_class_code": race.race_class_code,
            "_jv_blood_registration_number": (
                horse.blood_registration_number
            ),
            "_jv_abnormal_code": horse.abnormal_code,
            "_jv_popularity": horse.popularity,
        })

    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["race_date"] = pd.to_datetime(
            frame["race_date"],
            errors="raise",
        )
        frame = frame.sort_values(
            ["race_date", "race_id", "post_position"],
            kind="stable",
        ).reset_index(drop=True)

    if unmatched_se:
        warnings.append(
            f"{unmatched_se} SE records had no selected RA record"
        )
    if skipped_incomplete_se:
        warnings.append(
            f"{skipped_incomplete_se} incomplete/non-starter SE records "
            "were excluded from completed history"
        )

    report = JraVanParseReport(
        spec_version=JV_DATA_SPEC_VERSION,
        raw_records=raw_records,
        ra_records_seen=ra_seen,
        se_records_seen=se_seen,
        selected_ra_records=len(races),
        selected_se_records=len(horses),
        output_rows=int(len(frame)),
        output_races=(
            int(frame["race_id"].nunique())
            if not frame.empty
            else 0
        ),
        skipped_non_jra_ra=skipped_non_jra_ra,
        skipped_non_jra_se=skipped_non_jra_se,
        skipped_incomplete_se=skipped_incomplete_se,
        unmatched_se=unmatched_se,
        warnings=tuple(warnings),
    )
    return frame, report


def convert_raw_jsonl(
    *,
    input_path: str | Path,
    output_path: str | Path,
    report_path: str | Path,
    jra_only: bool = True,
    completed_only: bool = True,
) -> JraVanParseReport:
    frame, report = parse_raw_jsonl(
        input_path,
        jra_only=jra_only,
        completed_only=completed_only,
    )

    output_path = Path(output_path)
    report_path = Path(report_path)
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    frame.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )
    report_path.write_text(
        json.dumps(
            asdict(report),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return report
