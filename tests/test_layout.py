"""Layout checks that used to be items on a human QA checklist."""

import pytest

from tiktoks import safe
from tiktoks.safe import Box
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import THEMES
from tiktoks.text import fit, wrap

LONG_TITLE = (
    "A headline long enough that a naive character-count wrap would run it "
    "straight off the right edge of the canvas"
)


@pytest.fixture
def figure():
    slide = Slide("night")
    yield slide.figure
    slide.figure.clf()


def test_fit_never_exceeds_the_width(figure):
    font = {"fontfamily": ("DejaVu Sans",), "fontweight": "bold"}
    lines, size = fit(figure, LONG_TITLE, 904, size=78, min_size=46, max_lines=3, **font)
    from tiktoks.text import measure

    widest = max(measure(figure, line, fontsize=size, **font)[0] for line in lines)
    assert widest <= 904
    assert size <= 78


def test_wrap_honors_explicit_newlines(figure):
    lines = wrap(figure, "one\ntwo", 900, fontsize=40, fontfamily=("DejaVu Sans",))
    assert lines == ["one", "two"]


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_no_slide_content_lands_under_the_interface(theme):
    slide = Slide(
        theme,
        source="Source: World Bank, NY.GDP.PCAP.CD. Boundaries: Natural Earth.",
        cue="Swipe for the answer",
        badge="expert",
    )
    slide.kicker("Guess the map")
    slide.title(LONG_TITLE, hero=True)
    slide.dek("A dek long enough to reach down the frame and into the button rail zone.")
    slide.legend(["#111", "#222", "#333"], ["low", "high"], no_data=True)
    assert slide.check_layout() == []


def test_safe_area_can_be_switched_off():
    slide = Slide("night", safe_area=False)
    assert slide.floor == slide.height - slide.theme.margin_bottom
    assert slide.check_layout() == []


def test_safe_area_pushes_the_floor_above_the_caption():
    slide = Slide("night")
    assert slide.floor <= slide.height - safe.BOTTOM


def test_shared_slot_fits_both_slides():
    bare = Slide("night")
    bare.title("Short")
    crowded = Slide("night", source="Source: something", cue="Swipe")
    crowded.kicker("Answer")
    crowded.title("Short")
    crowded.dek("A fact that takes a couple of lines to say properly on the answer slide.")

    top, height = shared_slot(bare, crowded)
    for slide in (bare, crowded):
        slide_top, slide_height = slide.content_slot()
        assert top >= slide_top
        assert top + height <= slide_top + slide_height + 1


def test_rail_only_narrows_content_in_its_own_band():
    assert safe.right_edge_at(200, 400, 1032) == 1032
    assert safe.right_edge_at(900, 1000, 1032) < 1032


def test_boxes_intersect_only_on_real_overlap():
    assert Box(0, 0, 100, 100).intersects(Box(50, 50, 150, 150))
    assert not Box(0, 0, 100, 100).intersects(Box(100, 100, 200, 200))
    # Touching within tolerance is not a collision.
    assert not Box(0, 0, 100, 100).intersects(Box(99, 0, 200, 100))


def test_centered_stack_centers_in_its_band():
    slide = Slide("night")
    slide.centered_stack(
        [
            {"text": "Headline", "size": 80, "gap_after": 40},
            {"text": "Subhead", "size": 36},
        ],
        top=200,
        bottom=1000,
    )
    boxes = [box for kind, box in slide.boxes() if kind == "cover"]
    assert boxes
    top, bottom = min(b.y0 for b in boxes), max(b.y1 for b in boxes)
    assert top > 200 and bottom < 1000
    # Roughly centered in the band: equal slack above and below.
    assert abs((top - 200) - (1000 - bottom)) < 30


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_cover_slide_clears_the_interface(theme):
    slide = Slide(theme, source="Boundaries: Natural Earth")
    slide.scrim()
    slide.centered_stack(
        [
            {
                "text": "How many countries can you name?",
                "size": 82,
                "max_lines": 4,
                "gap_after": 54,
            },
            {"text": "Difficulty: Expert", "size": 40, "weight": "bold", "gap_after": 22},
            {"text": "10 countries", "size": 36, "gap_after": 40},
            {"text": "Comment your score below", "size": 32},
        ]
    )
    assert slide.check_layout() == []
