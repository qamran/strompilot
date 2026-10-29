"""Learning loop data models."""

from typing import Literal

from pydantic import BaseModel, field_validator

Verdict = Literal["too_early", "too_late", "good"]


class LearningError(Exception):
    """Invalid learning input: blank devices or bad windows."""


class Feedback(BaseModel):
    """One household verdict on a planned device run."""

    device: str
    verdict: Verdict
    note: str = ""

    @field_validator("device")
    @classmethod
    def _named_device(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("device must name the device")
        return stripped
