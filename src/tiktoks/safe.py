"""Where TikTok's own interface covers the frame.

A 1080x1920 export is not 1080x1920 of usable space. The app draws the caption,
username and music ticker across the bottom, a column of buttons down the right,
and its tab bar across the top. Anything the renderer puts in those bands is
covered in the feed.

The numbers below are measured against a screenshot, not read from a spec, so they
are approximate and worth rechecking when the app changes. `scripts/safe_overlay.py`
draws them over a rendered slide so a screenshot comparison takes a minute.
"""

from dataclasses import dataclass

from tiktoks.config import CANVAS_SIZE

WIDTH, HEIGHT = CANVAS_SIZE

# Tab bar ("For You" / "Following") and the search icon.
TOP = 130
# Caption, username, music marquee and, on carousels, the slide dots.
BOTTOM = 400
# The app crops a hair off each side on some aspect ratios.
SIDE = 48

# The button rail: avatar, like, comment, bookmark, share, spinning record. It does
# not run the full height, so text near the top can still use the full width.
RAIL_LEFT = 856
RAIL_TOP = 840
RAIL_BOTTOM = 1800

# Breathing room between content and a zone edge before it counts as a collision.
TOLERANCE = 2.0


@dataclass(frozen=True)
class Box:
    """A rectangle in slide coordinates, y increasing downward."""

    x0: float
    y0: float
    x1: float
    y1: float

    def intersects(self, other: "Box", tolerance: float = TOLERANCE) -> bool:
        return (
            self.x0 < other.x1 - tolerance
            and self.x1 > other.x0 + tolerance
            and self.y0 < other.y1 - tolerance
            and self.y1 > other.y0 + tolerance
        )


RAIL = Box(RAIL_LEFT, RAIL_TOP, WIDTH, RAIL_BOTTOM)

# Named zones, for reporting which one a collision hit.
ZONES = {
    "top bar": Box(0, 0, WIDTH, TOP),
    "caption": Box(0, HEIGHT - BOTTOM, WIDTH, HEIGHT),
    "left edge": Box(0, 0, SIDE, HEIGHT),
    "right edge": Box(WIDTH - SIDE, 0, WIDTH, HEIGHT),
    "button rail": RAIL,
}


def right_edge_at(top: float, bottom: float, default_right: float) -> float:
    """The rightmost x usable by content occupying a given vertical band.

    A legend or a footer line that runs the full content width would slide under
    the button rail. Text near the top of the frame is clear of it.
    """
    if bottom > RAIL_TOP and top < RAIL_BOTTOM:
        return min(default_right, RAIL_LEFT - 24)
    return default_right


def collisions(box: Box) -> list[str]:
    """Which reserved zones a box overlaps."""
    return [name for name, zone in ZONES.items() if box.intersects(zone)]
