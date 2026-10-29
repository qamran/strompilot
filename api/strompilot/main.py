"""Strompilot FastAPI application."""

from fastapi import FastAPI

from strompilot.contract import CONTRACT_VERSION, HealthResponse

app = FastAPI(title="Strompilot API", version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Report that the API is up and which contract version it speaks."""
    return HealthResponse(
        status="ok",
        service="strompilot-api",
        contract_version=CONTRACT_VERSION,
    )
