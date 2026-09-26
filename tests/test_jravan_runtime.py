from horse_racing_predictions.jravan_runtime import (
    classify_registration,
)


def test_runtime_guidance_detects_32bit_only_registration():
    guidance = classify_registration(
        registered_64bit=False,
        registered_32bit=True,
        python_bits=64,
    )
    assert any(
        "32-bit JV-Link is registered" in item
        for item in guidance
    )
    assert any(
        "64-bit JV-Link" in item
        for item in guidance
    )


def test_runtime_guidance_detects_missing_registration():
    guidance = classify_registration(
        registered_64bit=False,
        registered_32bit=False,
        python_bits=64,
    )
    assert any(
        "not registered in either" in item
        for item in guidance
    )


def test_runtime_guidance_accepts_matching_64bit_registration():
    guidance = classify_registration(
        registered_64bit=True,
        registered_32bit=False,
        python_bits=64,
    )
    assert any(
        "64-bit JV-Link registration exists" in item
        for item in guidance
    )
