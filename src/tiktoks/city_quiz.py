"""City globe quiz: a red dot on a borderless globe.

Two guesses per city. The country is worth a point and the city two more, so a
viewer who only knows the region still has something to put in the comments.
The prompt globe has no borders, which is the whole difficulty; the answer adds
the containing country back so the country point can be checked.
"""

from dataclasses import replace
from pathlib import Path

from tiktoks.geo_quiz import _cover, _scorecard
from tiktoks.io import read_yaml
from tiktoks.maps import (
    GLOBE_RED,
    containing_country,
    draw_backdrop,
    draw_city_globe,
    prepare_city_globe,
    prepare_world,
    quiz_countries,
    world_countries,
    world_land,
)
from tiktoks.post import Post
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import Theme, get_theme

SOURCE = "Cities: Esri. Land: Natural Earth"

COUNTRY_POINTS = 1
CITY_POINTS = 2

SPEC = {
    "cover_title": "Name the country. Then name the city.",
    "kicker": "City globe",
    "topic": "world geography city globe quiz",
    "hook": "Which country? Which city?",
}

SCORING = f"{COUNTRY_POINTS} point for the country. {CITY_POINTS} more for the city."


def max_score(total: int) -> int:
    return total * (COUNTRY_POINTS + CITY_POINTS)


def render_city_quiz(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = replace(get_theme(theme or config.get("theme")), map_panel=False)
    difficulty = config.get("difficulty", "medium")
    items = config["cities"]
    total = len(items)
    color = GLOBE_RED

    post = Post(
        slug=config.get("slug", config_path.parent.name),
        format="geo-quiz",
        theme=theme,
        output_dir=config_path.parent / theme.name,
        difficulty=difficulty,
        topic=config.get("topic", SPEC["topic"]),
        title=config.get("title"),
        caption=config.get("caption"),
        hashtags=config.get("hashtags", ["geography", "geoguessr", "quiz", "maps", "cities"]),
        sources=[
            "City locations: Esri World Cities",
            "Land: Natural Earth, 1:50 million",
            "Answer country: Natural Earth Admin 0 Countries, 1:10 million",
            "Cover geometry: CNN country polygons, 1:50 million",
        ],
        config_path=config_path,
    )

    cover = _cover(
        config,
        theme,
        difficulty,
        color,
        total,
        SPEC,
        unit="cities",
        cue=f"{SCORING} Score out of {max_score(total)}.",
    )
    backdrop, backdrop_aspect = cover.backdrop_axes()
    draw_backdrop(
        backdrop, prepare_world(world_countries()), theme=theme, aspect=backdrop_aspect, zoom=1.9
    )
    cover.scrim(0.22 if theme.name == "paper" else 0.3)
    cover_title = config.get("cover_title", SPEC["cover_title"])
    post.add(
        cover,
        kind="cover",
        alt=f"A world map behind the words: {cover_title} Difficulty {difficulty}, {total} cities.",
        title=cover_title,
    )

    built = [
        (
            item,
            _prompt(item, theme, difficulty, color, index, total),
            _answer(item, theme, color, index, total),
        )
        for index, item in enumerate(items, start=1)
    ]
    # One slot for the batch, so the globe does not jump between swipes.
    slot = shared_slot(*[slide for _, prompt, answer in built for slide in (prompt, answer)])
    land = world_land()
    countries = quiz_countries()

    for item, prompt, answer in built:
        lon, lat = float(item["lon"]), float(item["lat"])
        country = containing_country(countries, lon, lat)
        views = {
            "prompt": prepare_city_globe(land, lon, lat),
            "answer": prepare_city_globe(land, lon, lat, country),
        }
        for kind, slide in (("prompt", prompt), ("answer", answer)):
            axes, aspect = slide.map_axes(slot=slot, bleed=True)
            draw_city_globe(axes, views[kind], aspect=aspect)
            if kind == "prompt":
                alt = "A globe with no borders and one city marked with a red dot."
                title = None
            else:
                alt = (
                    f"{item['name']}, {item['country']}, marked on a globe with "
                    f"{item['country']} outlined. {item.get('fact', '')}"
                ).strip()
                title = f"{item['name']}, {item['country']}"
            post.add(slide, kind=kind, alt=alt, title=title)

    dek = f"{SCORING} Add it up out of {max_score(total)} and put your score in the comments"
    post.add(
        _scorecard(theme, difficulty, color, total, unit="cities", dek=dek),
        kind="scorecard",
        alt=dek,
    )
    post.finish()
    return post.paths


def _prompt(item: dict, theme: Theme, difficulty: str, color: str, index: int, total: int):
    slide = Slide(
        theme, source=SOURCE, cue="Swipe for answer", badge=f"{index}/{total}", badge_color=color
    )
    slide.kicker(f"{SPEC['kicker']} · {difficulty}")
    slide.title(item.get("hook") or SPEC["hook"])
    slide.dek(SCORING)
    return slide


def _answer(item: dict, theme: Theme, color: str, index: int, total: int) -> Slide:
    slide = Slide(theme, source=SOURCE, badge=f"{index}/{total}", badge_color=color)
    slide.kicker("Answer")
    slide.title(item["name"])
    slide.dek(item["country"], color=theme.text, weight="bold")
    slide.dek(item.get("fact", ""))
    return slide
