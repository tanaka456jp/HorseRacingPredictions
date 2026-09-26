from dataclasses import dataclass
from pathlib import Path
import zipfile

import pandas as pd

@dataclass(frozen=True)
class DataSourceSpec:
    name: str
    url: str
    license_label: str
    provenance: str
    redistribute_raw: bool
    use_scope: str

JRA_KAGGLE_1986_2021 = DataSourceSpec(
    name="JRA日本中央競馬会 Horse Racing Dataset",
    url="https://www.kaggle.com/datasets/takamotoki/jra-horse-racing-dataset",
    license_label="CC BY 4.0 (Kaggle metadata)",
    provenance="Dataset author states source data were scraped from netkeiba.",
    redistribute_raw=False,
    use_scope="historical_research_input_only",
)

COLUMN_ALIASES = {
    "race_id": ["レースID", "Race ID", "race_id"],
    "race_date": ["レース日付", "Race Day", "race_date"],
    "racecourse": ["競馬場名", "Racecourse Name", "racecourse"],
    "surface": ["芝・ダート区分", "Turf and Dirt Category", "surface"],
    "distance_m": ["距離(m)", "Distance(m)", "distance_m"],
    "weather": ["天候", "Weather", "weather"],
    "track_condition": ["馬場状態1", "Track Condition1", "track_condition"],
    "finish_position": ["着順", "FP", "finish_position"],
    "post_position": ["馬番", "PP", "post_position"],
    "horse_name": ["馬名", "Horse Name", "horse_name"],
    "sex": ["性別", "Sex", "sex"],
    "age": ["馬齢", "Age", "age"],
    "carried_weight": ["斤量", "Weight(Kg)", "carried_weight"],
    "jockey": ["騎手", "Jockey", "jockey"],
    "win_odds": ["単勝", "Win Odds(100Yen)", "win_odds"],
    "horse_weight": ["馬体重", "Horse Weight", "horse_weight"],
    "horse_weight_delta": [
        "場体重増減", "馬体重増減",
        "Horse Weight Gain and Loss", "horse_weight_delta"
    ],
    "trainer": ["調教師", "Trainer", "trainer"],
    "last_3f": ["上り", "上り3F", "Last 3F", "last_3f"],
    "corner_1": ["1コーナー", "Corner 1", "corner_1"],
    "corner_2": ["2コーナー", "Corner 2", "corner_2"],
    "corner_3": ["3コーナー", "Corner 3", "corner_3"],
    "corner_4": ["4コーナー", "Corner 4", "corner_4"],
    "race_class": ["競争条件", "Race Class", "race_class"],
    "graded_race": [
        "リステッド・重賞競走", "Graded Race", "graded_race"
    ],
}

REQUIRED_HISTORY_COLUMNS = {
    "race_id", "race_date", "finish_position", "horse_name", "win_odds"
}

REQUIRED_ENTRY_COLUMNS = {
    "race_id", "race_date", "horse_name"
}

NUMERIC_COLUMNS = {
    "finish_position", "win_odds", "distance_m", "post_position",
    "age", "carried_weight", "horse_weight", "horse_weight_delta",
    "last_3f", "corner_1", "corner_2", "corner_3", "corner_4",
}

CSV_ENCODINGS = (
    "utf-8-sig",
    "cp932",
    "shift_jis",
    "euc_jp",
    "utf-8",
)



def _read_csv_candidate(
    path: Path,
    *,
    encoding: str,
    low_memory: bool,
) -> pd.DataFrame:
    if not zipfile.is_zipfile(path):
        return pd.read_csv(
            path,
            encoding=encoding,
            low_memory=low_memory,
        )

    with zipfile.ZipFile(path) as archive:
        members = [
            name
            for name in archive.namelist()
            if not name.endswith("/")
        ]
        exact = [
            name
            for name in members
            if Path(name).name == path.name
        ]
        csv_members = [
            name
            for name in members
            if name.lower().endswith(".csv")
        ]

        if len(exact) == 1:
            member = exact[0]
        elif len(csv_members) == 1:
            member = csv_members[0]
        else:
            raise ValueError(
                "ZIP-wrapped CSV could not be resolved uniquely: "
                f"path={path}, members={members[:20]}"
            )

        with archive.open(member) as handle:
            return pd.read_csv(
                handle,
                encoding=encoding,
                low_memory=low_memory,
            )


def read_csv_flexible(
    path: str | Path,
    *,
    low_memory: bool = False,
) -> pd.DataFrame:
    path = Path(path)
    errors: list[Exception] = []
    for encoding in CSV_ENCODINGS:
        try:
            return _read_csv_candidate(
                path,
                encoding=encoding,
                low_memory=low_memory,
            )
        except UnicodeDecodeError as exc:
            errors.append(exc)
    if errors:
        raise errors[-1]
    raise RuntimeError(f"could not load CSV: {path}")

def _find_column(frame: pd.DataFrame, aliases: list[str]) -> str | None:
    for name in aliases:
        if name in frame.columns:
            return name
    return None

def normalize_jra_history(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = {}
    for target, aliases in COLUMN_ALIASES.items():
        source = _find_column(frame, aliases)
        if source is not None:
            normalized[target] = frame[source]

    out = pd.DataFrame(normalized).copy()
    missing = REQUIRED_HISTORY_COLUMNS - set(out.columns)
    if missing:
        raise ValueError(f"missing required columns: {sorted(missing)}")

    out["race_id"] = out["race_id"].astype(str)
    out["race_date"] = pd.to_datetime(out["race_date"], errors="raise")
    for column in NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    return out

def load_jra_history_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    errors: list[Exception] = []
    for encoding in CSV_ENCODINGS:
        try:
            raw = _read_csv_candidate(
                path,
                encoding=encoding,
                low_memory=False,
            )
            return normalize_jra_history(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append(exc)
    if errors:
        try:
            prefix_hex = path.read_bytes()[:16].hex()
        except OSError:
            prefix_hex = "unavailable"
        raise RuntimeError(
            "could not decode/normalize JRA history CSV "
            f"{path}; tried={CSV_ENCODINGS}; "
            f"is_zip={zipfile.is_zipfile(path)}; "
            f"prefix_hex={prefix_hex}; "
            "errors="
            + " | ".join(
                f"{type(error).__name__}: {error}"
                for error in errors
            )
        ) from errors[-1]
    raise RuntimeError(f"could not load CSV: {path}")


def normalize_future_entries(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = {}
    for target, aliases in COLUMN_ALIASES.items():
        source = _find_column(frame, aliases)
        if source is not None:
            normalized[target] = frame[source]

    out = pd.DataFrame(normalized).copy()
    missing = REQUIRED_ENTRY_COLUMNS - set(out.columns)
    if missing:
        raise ValueError(
            f"missing required entry columns: {sorted(missing)}"
        )

    out["race_id"] = out["race_id"].astype(str)
    out["race_date"] = pd.to_datetime(
        out["race_date"],
        errors="raise",
    )
    for column in NUMERIC_COLUMNS:
        if column in out.columns:
            out[column] = pd.to_numeric(
                out[column],
                errors="coerce",
            )
    return out


def load_future_entries_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    errors: list[Exception] = []
    for encoding in CSV_ENCODINGS:
        try:
            raw = pd.read_csv(
                path,
                encoding=encoding,
                low_memory=False,
            )
            return normalize_future_entries(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            errors.append(exc)
    if errors:
        raise RuntimeError(
            "could not decode/normalize future entries CSV "
            f"{path}; tried={CSV_ENCODINGS}; "
            f"last_error={errors[-1]}"
        ) from errors[-1]
    raise RuntimeError(f"could not load future entries CSV: {path}")
