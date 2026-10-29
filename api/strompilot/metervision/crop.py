"""Display cropping: cut the SAM box out of the meter photo."""

import io

from PIL import Image, UnidentifiedImageError

from .models import MeterError
from .sam import SegmentBox


def pick_box(boxes: list[SegmentBox]) -> SegmentBox | None:
    """Pick the best box: highest confidence, then largest area."""
    if not boxes:
        return None

    def rank(box: SegmentBox) -> tuple[float, int]:
        confidence = box.confidence if box.confidence is not None else -1.0
        area = max(box.x2 - box.x1, 0) * max(box.y2 - box.y1, 0)
        return (confidence, area)

    return max(boxes, key=rank)


def crop_to_box(photo: bytes, box: SegmentBox, margin: float = 0.1) -> bytes:
    """Crop the photo to the box plus margin, returned as PNG bytes."""
    try:
        image = Image.open(io.BytesIO(photo))
        image.load()
    except (UnidentifiedImageError, ValueError, OSError) as exc:
        raise MeterError(f"unreadable photo: {exc}") from exc
    scale_x = image.width / box.width if box.width > 0 else 1.0
    scale_y = image.height / box.height if box.height > 0 else 1.0
    left = box.x1 * scale_x
    top = box.y1 * scale_y
    right = box.x2 * scale_x
    bottom = box.y2 * scale_y
    pad_x = (right - left) * margin
    pad_y = (bottom - top) * margin
    crop = image.crop(
        (
            int(max(left - pad_x, 0)),
            int(max(top - pad_y, 0)),
            int(min(right + pad_x, image.width)),
            int(min(bottom + pad_y, image.height)),
        )
    )
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    return buffer.getvalue()
