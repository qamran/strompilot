"""Tests for the typed API contract stub."""

from strompilot.contract import CONTRACT_VERSION, HealthResponse


def test_contract_version_is_pinned() -> None:
    assert CONTRACT_VERSION == "0.6.0"


def test_health_response_schema_round_trip() -> None:
    model = HealthResponse(
        status="ok",
        service="strompilot-api",
        contract_version=CONTRACT_VERSION,
    )
    assert HealthResponse.model_validate(model.model_dump()) == model
