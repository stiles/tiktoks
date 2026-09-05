"""Draw the assumed TikTok interface zones over a rendered slide.

The numbers in `src/tiktoks/safe.py` were measured against a screenshot, not read
from a spec. Run this, put the result next to a real screenshot on a phone and
adjust the constants if the app has moved.

    uv run python scripts/safe_overlay.py <slide.png> [output.png]
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

from tiktoks import safe

FILL = {
    "top bar": (255, 80, 80, 90),
    "caption": (255, 80, 80, 90),
    "button rail": (80, 160, 255, 90),
    "left edge": (255, 210, 0, 70),
    "right edge": (255, 210, 0, 70),
}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1

    source = Path(argv[0])
    destination = Path(argv[1]) if len(argv) > 1 else source.with_name(f"{source.stem}-safe.png")

    base = Image.open(source).convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    for name, zone in safe.ZONES.items():
        draw.rectangle([zone.x0, zone.y0, zone.x1, zone.y1], fill=FILL.get(name, (255, 0, 0, 60)))
        draw.text((zone.x0 + 14, zone.y0 + 10), name, fill=(255, 255, 255, 230))

    Image.alpha_composite(base, layer).convert("RGB").save(destination)
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
