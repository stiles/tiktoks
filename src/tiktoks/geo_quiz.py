from pathlib import Path

from tiktoks.io import read_yaml
from tiktoks.maps import (
    MapView,
    draw_backdrop,
    draw_highlight,
    draw_outline,
    prepare_country,
    prepare_outline,
    prepare_world,
    quiz_countries,
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
# each tier gets a pool that rotates by position. The post slug shifts the start
# so a three-country quiz does not always open on the same three lines. Override
# per country with `hook:` in the batch config.
HOOKS = {
    "master": [
        "Just the outline. Name it.",
        "Still on a perfect score?",
        "No neighbors to help.",
        "Take a closer look.",
        "Trust your map memory.",
        "Lock in your answer.",
    ],
    "easy": [
        "Name it in three seconds.",
        "You learned this one in school.",
        "Too easy? Prove it.",
        "This should be instant.",
        "You know this outline.",
        "No excuse for missing this one.",
        "This one should go fast.",
        "Start the streak here.",
        "Do not overthink it.",
        "This is the freebie.",
        "Say it out loud.",
        "The easy one. Take it.",
        "If you pause, we have a problem.",
        "Point at the map and name it.",
        "Warm-up round.",
        "Everyone gets this.",
    ],
    "medium": [
        "Harder than it looks.",
        "Most people hesitate here.",
        "Know the shape, forget the name.",
        "You have seen this outline before.",
        "Recognize it yet?",
        "This one takes a second.",
        "Close enough to know, hard enough to miss.",
        "The outline helps less than you think.",
        "The name is on the tip of your tongue.",
        "Looks familiar. That's the trap.",
        "Don't name the neighbor.",
        "You will know it after the swipe.",
        "Easy to blank on.",
        "Not the one you think.",
        "Give it a beat.",
        "You have seen this on a wall map.",
    ],
    "hard": [
        "This one separates the map nerds.",
        "Borders will not help you here.",
        "Think smaller.",
        "Good luck with this one.",
        "This is where people lose the streak.",
        "You either know it or you don't.",
        "Big miss rate.",
        "This one gets guessed wrong a lot.",
        "The shape is the easy part.",
        "This one eats a point.",
        "Not a household name.",
        "Wrong neighbor is a popular guess.",
        "Pause if you have to.",
        "You have heard of it. You cannot place it.",
        "This is the trick one.",
        "Smaller than you are picturing.",
    ],
    "expert": [
        "Almost nobody gets this one.",
        "Blink and you would miss it.",
        "Good luck.",
        "This is the one that ends streaks.",
        "This one ruins perfect scores.",
        "Map nerd territory now.",
        "You only know this if you really know it.",
        "Tiny clue, big challenge.",
        "Speck on the map.",
        "No shame in missing it.",
        "If you get this, comment.",
        "This is the bonus round.",
        "I had to look this one up.",
        "This is the one to brag about.",
        "Most people skip this.",
        "The comments will fight on this one.",
    ],
}

VARIANTS = {
    "classic": {
        "borders": True,
        "cover_title": "How many countries can you name?",
        "kicker": "Name that country",
        "topic": "world geography",
        "mode": "two-beat",
        "frame_by_difficulty": {"easy": 1.0, "medium": 1.0, "hard": 1.0, "expert": 1.0},
    },
    "silhouette": {
        "borders": False,
        "cover_title": "Which country is this shape?",
        "kicker": "Shape only",
        "topic": "world geography silhouettes",
        "mode": "two-beat",
        # This format is about orientation by shape and surrounding land, so the
        # difficulty comes largely from how much context the frame keeps.
        "frame_by_difficulty": {"easy": 1.9, "medium": 1.55, "hard": 1.25, "expert": 1.0},
    },
    "progressive": {
        "borders": False,
        "cover_title": "Can you name it before the zoom-out?",
        "kicker": "Shape first",
        "topic": "world geography progressive reveals",
        "mode": "three-beat",
        # Prompt starts tighter, then the hint and answer share a wider frame.
        "prompt_frame_by_difficulty": {"easy": 1.15, "medium": 1.0, "hard": 0.88, "expert": 0.76},
        "reveal_frame_by_difficulty": {"easy": 2.1, "medium": 1.7, "hard": 1.35, "expert": 1.05},
        "reveal_borders_by_difficulty": {
            "easy": True,
            "medium": True,
            "hard": False,
            "expert": False,
        },
        "reveal_border_width_by_difficulty": {
            "easy": 0.9,
            "medium": 0.75,
        },
        "reveal_border_color": "muted",
        "hint_title": "A little more context.",
        "hint_cue": "Now take your best guess",
    },
}

COVER_TITLE = "How many countries can you name?"

MASTER_SPEC = {
    "cover_title": "Expert too easy? Try master.",
    "kicker": "Outline only",
    "topic": "world geography outlines",
    "mode": "two-beat",
}

SCORECARD = {
    "title": "How did you do?",
    "dek": "Tally your correct answers and put the number in the comments",
    "cue": "Comment your score",
}


def hook_for(item: dict, difficulty: str, index: int, *, salt: str = "") -> str:
    if item.get("hook"):
        return item["hook"]
    pool = HOOKS.get(difficulty, HOOKS["medium"])
    start = sum(ord(ch) for ch in salt) % len(pool) if salt else 0
    return pool[(start + index - 1) % len(pool)]


def render_geo_quiz(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme or config.get("theme"))
    difficulty = config.get("difficulty", "medium")
    variant = config.get("variant", "classic")
    if difficulty == "master" and variant != "classic":
        raise ValueError("Master uses isolated outlines; omit variant from the config.")
    if variant not in VARIANTS:
        raise ValueError(
            f"Unknown quiz variant {variant!r}. Options: {', '.join(sorted(VARIANTS))}"
        )
    variant_spec = MASTER_SPEC if difficulty == "master" else VARIANTS[variant]
    output_dir = config_path.parent / theme.name
    custom_source = config.get("countries_geojson")
    countries = quiz_countries(custom_source)
    cover_countries = world_countries(custom_source)
    color = theme.color_for(difficulty)
    items = config["countries"]
    total = len(items)

    post = Post(
        slug=config.get("slug", config_path.parent.name),
        format="geo-quiz",
        theme=theme,
        output_dir=output_dir,
        difficulty=difficulty,
        topic=config.get("topic", variant_spec["topic"]),
        title=config.get("title"),
        caption=config.get("caption"),
        hashtags=config.get("hashtags", ["geography", "geoguessr", "quiz", "maps"]),
        sources=[
            BOUNDARY_SOURCE,
            f"Country geometry: {custom_source}"
            if custom_source
            else "Country geometry: Natural Earth Admin 0 Countries, 1:10 million",
            f"Cover geometry: {custom_source}"
            if custom_source
            else "Cover geometry: CNN country polygons, 1:50 million",
        ],
        config_path=config_path,
    )

    cover = _cover(config, theme, difficulty, color, total, variant_spec)
    backdrop, backdrop_aspect = cover.backdrop_axes()
    draw_backdrop(
        backdrop, prepare_world(cover_countries), theme=theme, aspect=backdrop_aspect, zoom=1.9
    )
    cover.scrim(0.22 if theme.name == "paper" else 0.3)
    cover_title = config.get("cover_title", variant_spec["cover_title"])
    post.add(
        cover,
        kind="cover",
        alt=(
            f"A world map behind the words: {cover_title} "
            f"Difficulty {difficulty}, {total} countries."
        ),
        title=cover_title,
    )

    for index, item in enumerate(items, start=1):
        if difficulty == "master":
            _add_master_item(post, item, countries, theme, color, index, total)
        elif variant_spec["mode"] == "three-beat":
            _add_progressive_item(
                post, item, countries, theme, difficulty, color, index, total, variant_spec
            )
        else:
            _add_standard_item(
                post, item, countries, theme, difficulty, color, index, total, variant_spec
            )

    post.add(_scorecard(theme, difficulty, color, total), kind="scorecard", alt=SCORECARD["dek"])
    post.finish()
    return post.paths


def _view_for(item: dict, countries, frame_zoom: float) -> MapView:
    center = item.get("center")
    return prepare_country(
        countries,
        [item.get("match_name") or item["name"]],
        context=item.get("context", "regional"),
        center=tuple(center) if center else None,
        zoom=item.get("zoom", 1.0) * frame_zoom,
    )


def _add_master_item(post, item, countries, theme, color, index, total) -> None:
    outline = prepare_outline(countries, item.get("match_name") or item["name"])
    prompt = _prompt(item, theme, "master", color, index, total, MASTER_SPEC, salt=post.slug)
    prompt.dek("North is up. No surrounding land.")
    answer = _answer(item, theme, "master", color, index, total)
    slot = shared_slot(prompt, answer)
    axes, aspect = prompt.map_axes(slot=slot)
    draw_outline(axes, outline, theme=theme, aspect=aspect, color=color)
    post.add(
        prompt,
        kind="prompt",
        alt="An unlabeled country outline, north up, with no surrounding land.",
    )
    # Restore regional context for the reveal, even if a pool row requests a world view.
    reveal = _view_for({**item, "context": "regional"}, countries, 1.0)
    axes, aspect = answer.map_axes(slot=slot)
    draw_highlight(axes, reveal, theme=theme, aspect=aspect, color=color)
    post.add(answer, kind="answer", alt=_alt(item, "answer", False), title=item["name"])


def _add_standard_item(
    post: Post,
    item: dict,
    countries,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
    variant_spec: dict,
) -> None:
    view = _view_for(item, countries, variant_spec["frame_by_difficulty"].get(difficulty, 1.0))
    prompt = _prompt(item, theme, difficulty, color, index, total, variant_spec, salt=post.slug)
    answer = _answer(item, theme, difficulty, color, index, total)
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


def _add_progressive_item(
    post: Post,
    item: dict,
    countries,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
    variant_spec: dict,
) -> None:
    prompt_view = _view_for(
        item, countries, variant_spec["prompt_frame_by_difficulty"].get(difficulty, 1.0)
    )
    reveal_view = _view_for(
        item, countries, variant_spec["reveal_frame_by_difficulty"].get(difficulty, 1.0)
    )
    reveal_borders = variant_spec.get("reveal_borders_by_difficulty", {}).get(difficulty, False)
    reveal_border_width = variant_spec.get("reveal_border_width_by_difficulty", {}).get(difficulty)
    reveal_border_color = (
        theme.muted if variant_spec.get("reveal_border_color") == "muted" else None
    )
    prompt = _prompt(item, theme, difficulty, color, index, total, variant_spec, salt=post.slug)
    hint = _hint(item, theme, difficulty, color, index, total, variant_spec)
    answer = _answer(item, theme, difficulty, color, index, total)
    world = item.get("context") == "world"

    prompt_axes, prompt_aspect = prompt.map_axes(
        data_aspect=prompt_view.aspect if world else None,
        bleed=world,
    )
    draw_highlight(
        prompt_axes,
        prompt_view,
        theme=theme,
        aspect=prompt_aspect,
        color=color,
        borders=variant_spec["borders"],
    )
    post.add(prompt, kind="prompt", alt=_alt(item, "prompt", world), title=item["name"])

    reveal_slot = shared_slot(hint, answer)
    for kind, slide in (("hint", hint), ("answer", answer)):
        axes, aspect = slide.map_axes(
            slot=reveal_slot,
            data_aspect=reveal_view.aspect if world else None,
            bleed=world,
        )
        draw_highlight(
            axes,
            reveal_view,
            theme=theme,
            aspect=aspect,
            color=color,
            borders=reveal_borders,
            border_color=reveal_border_color,
            border_width=reveal_border_width,
        )
        post.add(slide, kind=kind, alt=_alt(item, kind, world), title=item["name"])


def _prompt(
    item: dict,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
    variant_spec: dict,
    *,
    salt: str = "",
) -> Slide:
    slide = Slide(
        theme,
        source=BOUNDARY_SOURCE,
        cue="Swipe for the answer" if variant_spec["mode"] == "two-beat" else "Need a hint?",
        badge=f"{index}/{total}",
        badge_color=color,
    )
    slide.kicker(f"{variant_spec['kicker']} · {difficulty}")
    slide.title(hook_for(item, difficulty, index, salt=salt))
    return slide


def _hint(
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
        cue=variant_spec.get("hint_cue", "Answer on the next slide"),
        badge=f"{index}/{total}",
        badge_color=color,
    )
    slide.kicker(f"Hint · {difficulty}")
    slide.title(item.get("hint", variant_spec.get("hint_title", "A little more context.")))
    return slide


def _answer(
    item: dict,
    theme: Theme,
    difficulty: str,
    color: str,
    index: int,
    total: int,
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
    if kind == "hint":
        return f"{scope} with one unlabeled country highlighted in a wider view."
    return f"{scope} with {item['name']} highlighted and named. {item.get('fact', '')}".strip()


__all__ = ["render_geo_quiz", "MapView"]
