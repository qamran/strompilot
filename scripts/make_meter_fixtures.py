"""Generate synthetic meter photos with known readings.

Draws three digital meter displays with 7-segment digits, each with a
known kWh value, plus a JSON sidecar the live checker asserts against.
Run from the repo root; outputs land in api/tests/fixtures/meter/.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("api/tests/fixtures/meter")

# Segments per digit: a top, b upper-right, c lower-right, d bottom,
# e lower-left, f upper-left, g middle.
SEGMENTS = {
    "0": "abcdef",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgedc",
    "7": "abc",
    "8": "abcdefg",
    "9": "abcdfg",
}


def draw_digit(draw: ImageDraw.ImageDraw, glyph: str, x: int, y: int) -> None:
    """Draw one 7-segment glyph at 64x112 pixels."""
    width, height, thick = 64, 112, 14
    mid = height // 2
    boxes = {
        "a": (x + thick, y, x + width - thick, y + thick),
        "g": (x + thick, y + mid - thick // 2, x + width - thick, y + mid + thick // 2),
        "d": (x + thick, y + height - thick, x + width - thick, y + height),
        "f": (x, y + thick, x + thick, y + mid),
        "b": (x + width - thick, y + thick, x + width, y + mid),
        "e": (x, y + mid, x + thick, y + height - thick),
        "c": (x + width - thick, y + mid, x + width, y + height - thick),
    }
    ink = (16, 20, 18)
    if glyph == ",":
        draw.rectangle((x + 20, y + height - 20, x + 44, y + height - 2), fill=ink)
        return
    for segment in SEGMENTS[glyph]:
        draw.rectangle(boxes[segment], fill=ink)


def draw_display(
    text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont
) -> Image.Image:
    """Draw one 800x600 meter photo showing the given register text."""
    photo = Image.new("RGB", (800, 600), (58, 60, 64))
    draw = ImageDraw.Draw(photo)
    draw.rectangle((70, 150, 730, 450), fill=(26, 26, 28))
    draw.rectangle((90, 170, 710, 430), fill=(206, 214, 188))
    draw.text((110, 176), "1.8.0", fill=(60, 64, 58), font=font)
    advance = 80
    total = len(text) * advance - 16
    cursor = (800 - total) // 2
    for glyph in text:
        draw_digit(draw, glyph, cursor, 230)
        cursor += advance
    draw.text((620, 380), "kWh", fill=(60, 64, 58), font=font)
    return photo


def main() -> None:
    """Render the three fixtures plus their expected values."""
    OUT.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=28)
    specs = [
        ("meter_clean", "04217,3", 4217.3),
        ("meter_obis", "12893,7", 12893.7),
        ("meter_dim", "00365,0", 365.0),
    ]
    sidecar = []
    for name, text, expected in specs:
        photo = draw_display(text, font)
        if name == "meter_dim":
            dimmed = photo.point(lambda channel: int(channel * 0.55))
            photo = dimmed.convert("RGB")
        photo.save(OUT / f"{name}.png")
        sidecar.append(
            {
                "name": name,
                "file": f"{name}.png",
                "expected_kwh": expected,
                "lcd": [90, 170, 710, 430],
            }
        )
    (OUT / "meter_fixtures.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(specs)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
