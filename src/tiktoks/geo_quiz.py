from pathlib import Path

from tiktoks.io import read_yaml
from tiktoks.maps import (
    MapView,
    draw_backdrop,
    draw_highlight,
    prepare_country,
    prepare_world,
    world_countries,
)
from tiktoks.post import Post
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import Theme, get_theme

BOUNDARY_SOURCE = "Boundaries: Natural Earth"

# The prompt slide's job is to stop a thumb, and an instruction does not. These
# stay clear of invented statistics: "9 out of 10 people miss this" is a number
# nobody measured.
#
# One hook per difficulty read as ten identical slides on the contact sheet, so
# each tier gets a pool that rotates by position. Override per country with
# `hook:` in the batch config.
HOOKS = {
    "easy": [
        "Name it in three seconds.",
        "You learned this one in school.",
        "Too easy? Prove it.",
        "This should be instant.",
    ],
    "medium": [
        "Harder than it looks.",
        "Most people hesitate here.",
        "Know the shape, forget the name.",
        "You have seen this outline before.",
    ],
    "hard": [
        "This one separates the map nerds.",
        "Borders will not help you here.",
        "Think smaller.",
        "Neighbors look almost identical.",
    ],
    "expert": [
        "Almost nobody gets this one.",
        "Blink and you would miss it.",
        "Good luck.",
        "This is the one that ends streaks.",
    ],
}

VARIANTS = {
    "classic": {
        "borders": True,
        "zoom_by_difficulty": {"easy": 1.0, "medium": 1.0, "hard": 1.0, "expert": 1.0},
        "cover_title": "How many countries can you name?",
        "kicker": "Name that country",
    },
    "silhouette": {
        "borders": False,
        # This format is about orientation by coastline and surrounding land, so
        # the difficulty comes largely from how much context the frame keeps.
        "zoom_by_difficulty": {"easy": 1.9, "medium": 1.55, "hard": 1.25, "expert": 1.0},
        "cover_title": "Which country is this shape?",
        "kicker": "Shape only",
    },
}


def hook_for(item: dict, difficulty: str, index: int) -> str:
    if item.get("hook"):
        return item["hook"]
    pool = HOOKS.get(difficulty, HOOKS["medium"])
    return pool[(index - 1) % len(pool)]


# The cover states the stakes before the first map. Starting on a map asks the
# viewer to work out what the post even is; a cover tells them and asks for a
# score in the same breath. Override with `cover_title` in the batch config.
COVER_TITLE = "How many countries can you name?"

SCORECARD = {
    "title": "How did you do?",
    "dek": "Count your correct answers and put the number in the comments. No looking it up.",
    "cue": "Comment your score",
}


def render_geo_quiz(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme or config.get("theme"))
    variant = config.get("variant", "classic")
    if variant not in VARIANTS:
        raise ValueError(
            f"Unknown quiz variant {variant!r}. Options: {', '.join(sorted(VARIANTS))}"
        )
    variant_spec = VARIANTS[variant]
    output_dir = config_path.parent / theme.name
    countries = world_countries(config.get("countries_geojson"))
    difficulty = config.get("difficulty", "medium")
    color = theme.color_for(difficulty)
    items = config["countries"]
    total = len(items)

    post = Post(
        slug=config.get("slug", config_path.parent.name),
        format="geo-quiz",
        theme=theme,
        output_dir=output_dir,
        difficulty=difficulty,
        topic=config.get(
            "topic",
            "world geography silhouettes" if variant == "silhouette" else "world geography",
        ),
        title=config.get("title"),
        caption=config.get("caption"),
        hashtags=config.get("hashtags", ["geography", "geoguessr", "quiz", "maps"]),
        sources=[BOUNDARY_SOURCE],
        config_path=config_path,
    )

    cover = _cover(config, theme, difficulty, color, total, variant_spec)
    backdrop, backdrop_aspect = cover.backdrop_axes()
    draw_backdrop(backdrop, prepare_world(countries), theme=theme, aspect=backdrop_aspect, zoom=1.9)
    # Paper's warm land and cool water need less wash than night or the cover map fades out.
    cover.scrim(0.22 if theme.name == "paper" else 0.3)
    post.add(
        cover,
        kind="cover",
        alt=f"A world map behind the words: {config.get('cover_title', variant_spec['cover_title'])} "
        f"Difficulty {difficulty}, {total} countries.",
        title=config.get("cover_title", variant_spec["cover_title"]),
    )

    for index, item in enumerate(items, start=1):
        center = item.get("center")
        zoom = item.get("zoom", 1.0) * variant_spec["zoom_by_difficulty"].get(difficulty, 1.0)
        view = prepare_country(
            countries,
            # The polygon name and the name on the answer slide are not always the
            # same. The boundary file still calls Eswatini "Swaziland".
            [item.get("match_name") or item["name"]],
            context=item.get("context", "regional"),
            center=tuple(center) if center else None,
            zoom=zoom,
        )
        prompt = _prompt(item, theme, difficulty, color, index, total, variant_spec)
        answer = _answer(item, theme, difficulty, color, index, total, variant_spec)
        # One frame across the pair, so the answer reads as a reveal and not a jump.
        slot = shared_slot(prompt, answer)
        world = item.get("context") == "world"

        for kind, slide in (("prompt", prompt), ("answer", answer)):
            axes, aspect = slide.map_axes(
                slot=slot, data_aspect=view.aspect if world else None, bleed=world
            )
            draw_highlight(
                axes,
                view,
                theme=theme,
                aspect=aspect,
                color=color,
                borders=variant_spec["borders"],
            )
            post.add(slide, kind=kind, alt=_alt(item, kind, world), title=item["name"])

    post.add(_scorecard(theme, difficulty, color, total), kind="scorecard", alt=SCORECARD["dek"])
    post.finish()
    return post.paths


def _prompt(
    item: dict,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
    variant_spec: dict,
) -> Slide:
    slide = Slide(
        theme,
        source=BOUNDARY_SOURCE,
        cue="Swipe for the answer",
        badge=f"{index}/{total}",
        badge_color=color,
    )
    slide.kicker(f"{variant_spec['kicker']} · {difficulty}")
    slide.title(hook_for(item, difficulty, index))
    return slide


def _answer(
    item: dict,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
    variant_spec: dict,
) -> Slide:
    slide = Slide(theme, source=BOUNDARY_SOURCE, badge=f"{index}/{total}", badge_color=color)
    slide.kicker("Answer")
    slide.title(item["name"])
    slide.dek(item.get("fact", ""))
    return slide


def _cover(
    config: dict, theme: Theme, difficulty: str, color: str, total: int, variant_spec: dict
) -> Slide:
    slide = Slide(theme, source=BOUNDARY_SOURCE)
    slide.centered_stack(
        [
            {
                "text": config.get("cover_title", variant_spec["cover_title"]),
                "size": int(theme.title_size * 1.05),
                "min_size": theme.title_min_size,
                "max_lines": 4,
                "font": theme.title_font,
                "weight": theme.title_weight,
                "leading": theme.title_leading,
                "color": theme.text,
                "gap_after": 54,
                "kind": "cover title",
            },
            {
                "text": f"Difficulty: {difficulty.capitalize()}",
                "size": 40,
                "weight": "bold",
                "color": color,
                "gap_after": 22,
                "kind": "cover difficulty",
            },
            {
                "text": f"{total} countries",
                "size": 36,
                "color": theme.text,
                "gap_after": 40,
                "kind": "cover count",
            },
            {
                "text": "Comment your score below",
                "size": 32,
                "color": theme.muted,
                "kind": "cover cue",
            },
        ]
    )
    return slide


def _scorecard(theme: Theme, difficulty: str, color: str, total: int) -> Slide:
    slide = Slide(theme, cue=SCORECARD["cue"], badge=difficulty, badge_color=color)
    slide.kicker(f"{total} countries")
    slide.title(SCORECARD["title"])
    slide.dek(SCORECARD["dek"])
    return slide


def _alt(item: dict, kind: str, world: bool) -> str:
    scope = "A world map" if world else "A regional map"
    if kind == "prompt":
        return f"{scope} with one unlabeled country highlighted."
    return f"{scope} with {item['name']} highlighted and named. {item.get('fact', '')}".strip()


__all__ = ["render_geo_quiz", "MapView"]
