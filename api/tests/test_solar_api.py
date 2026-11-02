"""Tests for the solar teaser HTTP API."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from strompilot.main import app, get_image_client, get_sam_client
from strompilot.metervision.sam import SegmentBox
from tests.fakes import FakeSam

from .auth_helpers import sign_in


def png(width: int = 800, height: int = 600) -> bytes:
    """One plain house-photo-sized PNG upload."""
    image = Image.new("RGB", (width, height), (200, 200, 200))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def roof_box() -> SegmentBox:
    """The main roof on the 800x600 test photo."""
    return SegmentBox(
        x1=100, y1=50, x2=500, y2=250, width=800, height=600, confidence=0.9
    )


class FakeImages:
    """Scripted image editor that records prompts."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def edit(self, image: bytes, prompt: str, size: str = "1536x1024") -> bytes:
        del image, size
        self.prompts.append(prompt)
        return b"preview-bytes"


@pytest.fixture
def solar_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """Signed-in client with scripted SAM and image editing."""
    monkeypatch.setenv("MEMORY_DB", str(tmp_path / "memory.db"))
    app.dependency_overrides[get_sam_client] = lambda: FakeSam([[roof_box()]] * 8)
    app.dependency_overrides[get_image_client] = lambda: FakeImages()
    client = TestClient(app)
    sign_in(client, "h1")
    yield client
    app.dependency_overrides.clear()


def test_measure_outlines_roof_and_counts_panels(
    solar_setup: TestClient,
) -> None:
    """A roof photo returns boxes plus a panel estimate with assumptions."""
    res = solar_setup.post(
        "/solar/measure?household_id=h1&roof_width_m=10",
        files={"file": ("house.png", png(), "image/png")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["width"] == 800
    assert len(body["boxes"]) == 1
    assert body["boxes"][0]["x1"] == 100
    assert body["estimate"]["panels"] == 17
    assert body["estimate"]["kwp"] == pytest.approx(6.8)
    assert len(body["estimate"]["assumptions"]) >= 3
    assert body["household_id"] == "h1"


def test_measure_needs_a_session(solar_setup: TestClient) -> None:
    """Anonymous and foreign measure calls are refused."""
    anon = TestClient(app)
    res = anon.post(
        "/solar/measure?household_id=h1",
        files={"file": ("house.png", png(), "image/png")},
    )
    assert res.status_code == 401
    res = solar_setup.post(
        "/solar/measure?household_id=h2",
        files={"file": ("house.png", png(), "image/png")},
    )
    assert res.status_code == 403


def test_measure_rejects_non_images(solar_setup: TestClient) -> None:
    """A text file is not a house photo."""
    res = solar_setup.post(
        "/solar/measure?household_id=h1",
        files={"file": ("notes.txt", b"4217", "text/plain")},
    )
    assert res.status_code == 422


def test_preview_edits_the_house_photo(solar_setup: TestClient) -> None:
    """A preview returns edited bytes with an AI label."""
    res = solar_setup.post(
        "/solar/preview?household_id=h1&style=solar&lang=en",
        files={"file": ("house.png", png(), "image/png")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["image_data_url"].startswith("data:image/png;base64,")
    assert body["style"] == "solar"
    assert "AI" in body["ai_label"]
    bad = solar_setup.post(
        "/solar/preview?household_id=h1&style=pool",
        files={"file": ("house.png", png(), "image/png")},
    )
    assert bad.status_code == 422
