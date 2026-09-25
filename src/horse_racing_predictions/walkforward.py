from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class WalkForwardFold:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_index: list[int]
    test_index: list[int]

def expanding_walk_forward_splits(
    frame: pd.DataFrame,
    date_col: str,
    min_train_dates: int = 30,
    test_dates: int = 7,
    gap_dates: int = 0,
):
    if min_train_dates <= 0 or test_dates <= 0 or gap_dates < 0:
        raise ValueError("invalid walk-forward window")

    dates = pd.to_datetime(frame[date_col], errors="raise").dt.normalize()
    unique_dates = sorted(dates.dropna().unique())
    cursor = min_train_dates

    while cursor + gap_dates < len(unique_dates):
        test_start_pos = cursor + gap_dates
        test_end_pos = min(test_start_pos + test_dates, len(unique_dates))
        if test_start_pos >= test_end_pos:
            break

        train_allowed = set(unique_dates[:cursor])
        test_allowed = set(unique_dates[test_start_pos:test_end_pos])
        train_idx = frame.index[dates.isin(train_allowed)].tolist()
        test_idx = frame.index[dates.isin(test_allowed)].tolist()

        if train_idx and test_idx:
            yield WalkForwardFold(
                train_start=pd.Timestamp(unique_dates[0]),
                train_end=pd.Timestamp(unique_dates[cursor - 1]),
                test_start=pd.Timestamp(unique_dates[test_start_pos]),
                test_end=pd.Timestamp(unique_dates[test_end_pos - 1]),
                train_index=train_idx,
                test_index=test_idx,
            )
        cursor = test_end_pos
