from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from .modeling import CatBoostProbabilityModel


MODEL_FILENAME = "model.cbm"
MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class ChampionManifest:
    model_version: str
    experiment_id: str
    model_kind: str
    feature_columns: tuple[str, ...]
    categorical_columns: tuple[str, ...]
    train_start: str
    train_end: str
    source_id: str
    validation_brier: float
    validation_log_loss: float
    validation_research_roi: float
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        feature_columns,
        categorical_columns,
        train_start: str,
        train_end: str,
        source_id: str,
        model_version: str = "champion-v7",
        experiment_id: str = "v7-catboost-recent-form",
        validation_brier: float = 0.061549,
        validation_log_loss: float = 0.223565,
        validation_research_roi: float = -0.0190,
    ) -> "ChampionManifest":
        return cls(
            model_version=model_version,
            experiment_id=experiment_id,
            model_kind="catboost",
            feature_columns=tuple(feature_columns),
            categorical_columns=tuple(categorical_columns),
            train_start=train_start,
            train_end=train_end,
            source_id=source_id,
            validation_brier=float(validation_brier),
            validation_log_loss=float(validation_log_loss),
            validation_research_roi=float(validation_research_roi),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @classmethod
    def from_dict(cls, value: dict) -> "ChampionManifest":
        return cls(
            model_version=str(value["model_version"]),
            experiment_id=str(value["experiment_id"]),
            model_kind=str(value["model_kind"]),
            feature_columns=tuple(value["feature_columns"]),
            categorical_columns=tuple(value["categorical_columns"]),
            train_start=str(value["train_start"]),
            train_end=str(value["train_end"]),
            source_id=str(value["source_id"]),
            validation_brier=float(value["validation_brier"]),
            validation_log_loss=float(value["validation_log_loss"]),
            validation_research_roi=float(
                value["validation_research_roi"]
            ),
            created_at=str(value["created_at"]),
        )


@dataclass
class LoadedChampion:
    model: CatBoostProbabilityModel
    manifest: ChampionManifest


def save_champion_artifact(
    model: CatBoostProbabilityModel,
    manifest: ChampionManifest,
    directory: str | Path,
) -> Path:
    if model.model is None:
        raise ValueError("cannot save an unfitted CatBoost model")
    if tuple(model.feature_columns) != manifest.feature_columns:
        raise ValueError(
            "model feature columns do not match champion manifest"
        )

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)

    model_path = directory / MODEL_FILENAME
    manifest_path = directory / MANIFEST_FILENAME

    model.model.save_model(str(model_path))
    manifest_path.write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return directory


def load_champion_artifact(
    directory: str | Path,
) -> LoadedChampion:
    directory = Path(directory)
    manifest_path = directory / MANIFEST_FILENAME
    model_path = directory / MODEL_FILENAME

    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)
    if not model_path.exists():
        raise FileNotFoundError(model_path)

    manifest = ChampionManifest.from_dict(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    if manifest.model_kind != "catboost":
        raise ValueError(
            f"unsupported champion model_kind: {manifest.model_kind}"
        )

    try:
        from catboost import CatBoostClassifier
    except ImportError as exc:
        raise RuntimeError(
            "Loading the Champion requires the research extra: "
            "pip install -e '.[research]'"
        ) from exc

    wrapper = CatBoostProbabilityModel(
        list(manifest.feature_columns)
    )
    native = CatBoostClassifier()
    native.load_model(str(model_path))
    wrapper.model = native
    wrapper.categorical_columns = list(
        manifest.categorical_columns
    )
    return LoadedChampion(
        model=wrapper,
        manifest=manifest,
    )
