from pathlib import Path

from tiktoks.io import read_yaml
from tiktoks.maps import MapView, draw_highlight, prepare_country, world_countries
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import Theme, get_theme

BOUNDARY_SOURCE = "Boundaries: Natural Earth"


def render_geo_quiz(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme or config.get("theme"))
    output_dir = config_path.parent / config.get("output_dir", "output") / theme.name
    countries = world_countries(config.get("countries_geojson"))
    difficulty = config.get("difficulty", "medium")
    color = theme.color_for(difficulty)

    rendered: list[Path] = []
    for index, item in enumerate(config["countries"], start=1):
        center = item.get("center")
        view = prepare_country(
            countries,
            [item["name"]],
            context=item.get("context", "regional"),
            center=tuple(center) if center else None,
            zoom=item.get("zoom", 1.0),
        )
        pair = {
            "prompt": _prompt(item, theme, difficulty, color),
            "answer": _answer(item, theme, difficulty, color),
        }
        # One frame across the pair, so the answer reads as a reveal and not a jump.
        slot = shared_slot(*pair.values())
        world = item.get("context") == "world"

        for kind, slide in pair.items():
            axes = slide.map_axes(
                slot=slot, data_aspect=view.aspect if world else None, bleed=world
            )
            draw_highlight(axes, view, theme=theme, aspect=slide.map_aspect, color=color)
            rendered.append(
                slide.save(output_dir / f"geo-quiz-{difficulty}-{index:02d}-{kind}.png")
            )
    return rendered


def _prompt(item: dict, theme: Theme, difficulty: str, color: str) -> Slide:
    slide = Slide(
        theme,
        source=BOUNDARY_SOURCE,
        cue="Swipe for the answer",
        badge=difficulty,
        badge_color=color,
    )
    slide.kicker("Name that country")
    slide.title(item.get("prompt", "Which country is highlighted?"))
    return slide


def _answer(item: dict, theme: Theme, difficulty: str, color: str) -> Slide:
    slide = Slide(theme, source=BOUNDARY_SOURCE, badge=difficulty, badge_color=color)
    slide.kicker("Answer")
    slide.title(item["name"])
    slide.dek(item.get("fact", ""))
    return slide


__all__ = ["render_geo_quiz", "MapView"]
