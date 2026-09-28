import pytest

from horse_racing_predictions.market_residual_v12 import (
    MarketResidualRegressor,
)
from horse_racing_predictions.residual_v12_artifact import (
    ARTIFACT_VERSION,
    FrozenResidualV12Manifest,
)


def _manifest():
    model = MarketResidualRegressor(
        ["a", "b"],
        iterations=350,
    )
    model.categorical_columns = ["b"]
    return FrozenResidualV12Manifest.create(
        model,
        train_start="2017-01-05",
        train_end="2021-07-31",
    )


def test_frozen_residual_manifest_accepts_exact_definition():
    manifest = _manifest()

    manifest.validate_expected(
        feature_columns=["a", "b"],
        train_start="2017-01-05",
        train_end="2021-07-31",
        iterations=350,
    )

    assert manifest.artifact_version == ARTIFACT_VERSION
    assert manifest.fixed_gamma == 4.0


def test_frozen_residual_manifest_fails_closed_on_definition_change():
    manifest = _manifest()

    with pytest.raises(
        ValueError,
        match="cache manifest does not match",
    ):
        manifest.validate_expected(
            feature_columns=["a", "changed"],
            train_start="2017-01-05",
            train_end="2021-07-31",
            iterations=350,
        )
