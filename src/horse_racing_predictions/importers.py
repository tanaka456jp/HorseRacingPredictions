from pathlib import Path
import pandas as pd

COLUMN_ALIASES = {
    "race_id": ["レースID", "Race ID", "race_id"],
    "race_date": ["レース日付", "Race Day", "race_date"],
    "racecourse": ["競馬場名", "Racecourse Name", "racecourse"],
    "horse_name": ["馬名", "Horse Name", "horse_name"],
    "finish_position": ["着順", "Finish Position", "finish_position"],
    "odds": ["単勝", "Win Odds", "odds"],
}

def _find_column(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

def load_free_race_result_csv(path):
    path = Path(path)
    last_error = None
    for encoding in ("utf-8-sig", "cp932", "utf-8"):
        try:
            df = pd.read_csv(path, encoding=encoding, low_memory=False)
            break
        except Exception as e:
            last_error = e
    else:
        raise last_error

    normalized = {}
    for target, names in COLUMN_ALIASES.items():
        source = _find_column(df, names)
        if source is not None:
            normalized[target] = df[source]
    out = pd.DataFrame(normalized)
    if "race_id" not in out.columns:
        raise ValueError("race_id column could not be detected")
    return out
