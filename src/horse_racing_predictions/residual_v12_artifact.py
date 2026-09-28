from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .market_residual_v12 import MarketResidualRegressor
from .market_residual_v12_holdout import FIXED_GAMMA


MODEL_FILENAME = "model.cbm"
MANIFEST_FILENAME = "manifest.json"
ARTIFACT_VERSION = "market-residual-v12-frozen-cache-v1"


@dataclass(frozen=True)
class FrozenResidualV12Manifest:
    artifact_version: str
    feature_columns: tuple[str, ...]
    categorical_columns: tuple[str, ...]
    train_start: str
    train_end: str
    iterations: int
    depth: int
    learning_rate: float
    random_seed: int
    fixed_gamma: float

    @classmethod
    def create(
        cls,
        model: MarketResidualRegressor,
        *,
        train_start: str,
        train_end: str,
        fixed_gamma: float = FIXED_GAMMA,
    ) -> "FrozenResidualV12Manifest":
        return cls(
            artifact_version=ARTIFACT_VERSION,
            feature_columns=tuple(model.feature_columns),
            categorical_columns=tuple(model.categorical_columns),
            train_start=str(train_start),
            train_end=str(train_end),
            iterations=int(model.iterations),
            depth=int(model.depth),
            learning_rate=float(model.learning_rate),
            random_seed=int(model.random_seed),
            fixed_gamma=float(fixed_gamma),
        )

    @classmethod
    def from_dict(cls, value: dict) -> "FrozenResidualV12Manifest":
        return cls(
            artifact_version=str(value["artifact_version"]),
            feature_columns=tuple(value["feature_columns"]),
            categorical_columns=tuple(value["categorical_columns"]),
            train_start=str(value["train_start"]),
            train_end=str(value["train_end"]),
            iterations=int(value["iterations"]),
            depth=int(value["depth"]),
            learning_rate=float(value["learning_rate"]),
            random_seed=int(value["random_seed"]),
            fixed_gamma=float(value["fixed_gamma"]),
        )

    def validate_expected(
        self,
        *,
        feature_columns,
        train_start: str,
        train_end: str,
        iterations: int,
        fixed_gamma: float = FIXED_GAMMA,
    ) -> None:
        expected = {
            "artifact_version": ARTIFACT_VERSION,
            "feature_columns": tuple(feature_columns),
            "train_start": str(train_start),
            "train_end": str(train_end),
            "iterations": int(iterations),
            "depth": 7,
            "learning_rate": 0.05,
            "random_seed": 42,
            "fixed_gamma": float(fixed_gamma),
        }
        actual = {
            "artifact_version": self.artifact_version,
            "feature_columns": self.feature_columns,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "iterations": self.iterations,
            "depth": self.depth,
            "learning_rate": self.learning_rate,
            "random_seed": self.random_seed,
            "fixed_gamma": self.fixed_gamma,
        }
        if actual != expected:
            raise ValueError(
                "frozen Residual v12 cache manifest does not match "
                "the expected model definition"
            )


def save_frozen_residual_v12_model(
    model: MarketResidualRegressor,
    directory: str | Path,
    *,
    train_start: str,
    train_end: str,
    fixed_gamma: float = FIXED_GAMMA,
) -> Path:
    if model.model is None:
        raise ValueError("cannot cache an unfitted Residual v12 model")

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = FrozenResidualV12Manifest.create(
        model,
        train_start=train_start,
        train_end=train_end,
        fixed_gamma=fixed_gamma,
    )

    model.model.save_model(str(directory / MODEL_FILENAME))
    (directory / MANIFEST_FILENAME).write_text(
        json.dumps(asdict(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return directory


def load_frozen_residual_v12_model(
    directory: str | Path,
    *,
    expected_feature_columns,
    train_start: str,
    train_end: str,
    iterations: int,
    fixed_gamma: float = FIXED_GAMMA,
) -> tuple[MarketResidualRegressor, FrozenResidualV12Manifest]:
    directory = Path(directory)
    model_path = directory / MODEL_FILENAME
    manifest_path = directory / MANIFEST_FILENAME
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not manifest_path.exists():
        raise FileNotFoundError(manifest_path)

    manifest = FrozenResidualV12Manifest.from_dict(
        json.loads(manifest_path.read_text(encoding="utf-8"))
    )
    manifest.validate_expected(
        feature_columns=expected_feature_columns,
        train_start=train_start,
        train_end=train_end,
        iterations=iterations,
        fixed_gamma=fixed_gamma,
    )

    try:
        from catboost import CatBoostRegressor
    except ImportError as exc:
        raise RuntimeError(
            "Loading the frozen Residual v12 model requires the "
            "research extra: pip install -e '.[research]'"
        ) from exc

    wrapper = MarketResidualRegressor(
        list(manifest.feature_columns),
        iterations=manifest.iterations,
        depth=manifest.depth,
        learning_rate=manifest.learning_rate,
        random_seed=manifest.random_seed,
    )
    native = CatBoostRegressor()
    native.load_model(str(model_path))
    wrapper.model = native
    wrapper.categorical_columns = list(manifest.categorical_columns)
    return wrapper, manifest
