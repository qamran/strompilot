"""Generate synthetic meter photos with known readings.

Draws three German-style eHZ household meters in portrait: light grey
housing, black LCD bezel with 7-segment register, OBIS code, printed
serial plate with barcode, and a terminal cover with screws. Each has a
known kWh value plus a known serial, with a JSON sidecar the live
checker asserts against. Run from the repo root; outputs land in
api/tests/fixtures/meter/.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("api/tests/fixtures/meter")

WIDTH, HEIGHT = 760, 1020
HOUSING = (96, 150, 664, 960)
LCD_OUTER = (150, 330, 610, 570)
LCD_INNER = (170, 350, 590, 550)

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


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Prefer Arial for printed labels, falling back to the default."""
    for candidate in (
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def draw_digit(draw: ImageDraw.ImageDraw, glyph: str, x: int, y: int) -> None:
    """Draw one 7-segment glyph at 46x88 pixels with unlit ghosts."""
    width, height, thick = 46, 88, 10
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
    ghost = (190, 198, 172)
    ink = (14, 18, 14)
    if glyph == ",":
        draw.rectangle((x + 13, y + height - 16, x + 31, y + height - 2), fill=ink)
        return
    for segment, box in boxes.items():
        draw.rectangle(box, fill=ghost)
    for segment in SEGMENTS[glyph]:
        draw.rectangle(boxes[segment], fill=ink)


def draw_barcode(draw: ImageDraw.ImageDraw, serial: str, x: int, y: int) -> None:
    """Draw a deterministic barcode strip derived from the serial."""
    cursor = x
    for char in serial:
        width = 2 + (ord(char) % 4)
        if ord(char) % 3:
            draw.rectangle((cursor, y, cursor + width, y + 54), fill=(30, 30, 32))
        cursor += width + 2 + (ord(char) % 3)


def draw_screw(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """Draw one housing screw with a slot."""
    draw.ellipse((cx - 11, cy - 11, cx + 11, cy + 11), fill=(105, 108, 112))
    draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=(140, 143, 148))
    draw.line((cx - 6, cy + 2, cx + 6, cy - 2), fill=(70, 72, 76), width=2)


def draw_meter(
    text: str,
    serial: str,
    year: str,
    small: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    label: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> Image.Image:
    """Draw one portrait eHZ meter photo with register plus serial."""
    photo = Image.new("RGB", (WIDTH, HEIGHT), (52, 55, 60))
    draw = ImageDraw.Draw(photo)
    for row in range(HEIGHT):
        shade = int(52 + 10 * row / HEIGHT)
        draw.line([(0, row), (WIDTH, row)], fill=(shade, shade + 3, shade + 8))
    # Drop shadow, then the light grey housing.
    draw.rounded_rectangle(
        [HOUSING[0] + 14, HOUSING[1] + 18, HOUSING[2] + 14, HOUSING[3] + 10],
        radius=26,
        fill=(28, 30, 34),
    )
    draw.rounded_rectangle(HOUSING, radius=24, fill=(214, 217, 212))
    draw.rounded_rectangle(HOUSING, radius=24, outline=(150, 153, 148), width=3)
    draw.line(
        [(HOUSING[0] + 24, HOUSING[1] + 6), (HOUSING[2] - 24, HOUSING[1] + 6)],
        fill=(235, 237, 233),
        width=3,
    )
    # Printed header block.
    draw.text((130, 178), "eHZ", fill=(40, 42, 46), font=title)
    draw.text((130, 228), "Drehstromzähler  3x230/400V  50Hz", fill=(70, 72, 76), font=label)
    draw.text((130, 262), f"Cl. B   {year}   MID", fill=(90, 92, 96), font=label)
    draw_screw(draw, 128, 900)
    draw_screw(draw, 632, 900)
    # LCD window: black bezel, lit panel, soft glare.
    draw.rounded_rectangle(LCD_OUTER, radius=10, fill=(18, 18, 20))
    draw.rounded_rectangle(LCD_INNER, radius=4, fill=(199, 208, 182))
    draw.polygon(
        [(170, 350), (215, 350), (175, 550), (170, 550)], fill=(216, 224, 198)
    )
    draw.text((190, 358), "1.8.0", fill=(60, 64, 58), font=label)
    advance = 56
    total = len(text) * advance - 10
    cursor = (LCD_INNER[0] + LCD_INNER[2] - total) // 2
    for glyph in text:
        draw_digit(draw, glyph, cursor, 402)
        cursor += advance
    draw.text((516, 502), "kWh", fill=(60, 64, 58), font=label)
    # Serial plate with barcode below the display.
    draw.text((150, 612), f"Nr {serial}", fill=(35, 37, 40), font=title)
    draw_barcode(draw, serial, 150, 664)
    draw.text((150, 730), "1.8.0 Bezug Gesamt", fill=(90, 92, 96), font=small)
    # Terminal cover seam.
    draw.line([(110, 850), (650, 850)], fill=(150, 153, 148), width=3)
    draw.text((150, 800), "Klemmendeckel nur durch Fachkraft öffnen", fill=(110, 112, 116), font=small)
    return photo


def main() -> None:
    """Render the three fixtures plus their expected values."""
    OUT.mkdir(parents=True, exist_ok=True)
    small = load_font(22)
    label = load_font(28)
    title = load_font(44)
    specs = [
        ("meter_clean", "04217,3", 4217.3, "1ESY1162345678", "2023"),
        ("meter_obis", "12893,7", 12893.7, "1ESY1162345679", "2021"),
        ("meter_dim", "00365,0", 365.0, "1ESY1162345680", "2019"),
    ]
    sidecar = []
    for name, text, expected, serial, year in specs:
        photo = draw_meter(text, serial, year, small, label, title)
        if name == "meter_dim":
            dimmed = photo.point(lambda channel: int(channel * 0.55))
            photo = dimmed.convert("RGB")
        photo.save(OUT / f"{name}.png")
        sidecar.append(
            {
                "name": name,
                "file": f"{name}.png",
                "expected_kwh": expected,
                "expected_serial": serial,
                "lcd": list(LCD_INNER),
            }
        )
    (OUT / "meter_fixtures.json").write_text(
        json.dumps(sidecar, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(specs)} fixtures to {OUT}")


if __name__ == "__main__":
    main()
