"""Muse Image client for the monthly report illustration."""

import base64
import io

import httpx
from PIL import Image, UnidentifiedImageError

from strompilot.llm.client import META_BASE_URL
from strompilot.llm.types import LlmError

IMAGE_MODEL = "muse-image-1.0"
IMAGE_SIZE = "1536x1024"
IMAGE_TIMEOUT_SECONDS = 300.0


class ImageClient:
    """Generates one image per call over the images endpoint."""

    def __init__(
        self,
        api_key: str,
        base_url: str = META_BASE_URL,
        timeout: float = IMAGE_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def edit(self, image: bytes, prompt: str, size: str = IMAGE_SIZE) -> bytes:
        """Edit one image from a prompt, returning the raw result bytes."""
        if not prompt.strip():
            raise LlmError("prompt must not be blank")
        if not image:
            raise LlmError("image must not be empty")
        try:
            with Image.open(io.BytesIO(image)) as parsed:
                picture_format = (parsed.format or "PNG").lower()
        except UnidentifiedImageError as exc:
            raise LlmError("image unreadable") from exc
        mime = f"image/{'jpeg' if picture_format == 'jpeg' else picture_format}"
        try:
            response = httpx.post(
                f"{self._base_url}/images/edits",
                headers={"Authorization": f"Bearer {self._api_key}"},
                files={"image": (f"house.{picture_format}", image, mime)},
                data={
                    "model": IMAGE_MODEL,
                    "prompt": prompt,
                    "size": size,
                    "response_format": "b64_json",
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LlmError(f"request failed: {exc}") from exc
        if response.status_code != 200:
            raise LlmError(f"HTTP {response.status_code} from {self._base_url}")
        try:
            data = response.json()["data"][0]["b64_json"]
            return base64.b64decode(data)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("unreadable image body") from exc

    def generate(self, prompt: str, size: str = IMAGE_SIZE) -> bytes:
        """Generate one image, returning its raw bytes."""
        if not prompt.strip():
            raise LlmError("prompt must not be blank")
        try:
            response = httpx.post(
                f"{self._base_url}/images/generations",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": IMAGE_MODEL,
                    "prompt": prompt,
                    "size": size,
                    "response_format": "b64_json",
                },
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise LlmError(f"request failed: {exc}") from exc
        if response.status_code != 200:
            raise LlmError(f"HTTP {response.status_code} from {self._base_url}")
        try:
            data = response.json()["data"][0]["b64_json"]
            return base64.b64decode(data)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LlmError("unreadable image body") from exc
