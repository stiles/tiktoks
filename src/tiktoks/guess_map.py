from pathlib import Path

import pandas as pd

from tiktoks import catalog
from tiktoks.config import GUESS_MAP_CATALOG_PATH, POSTS_DIR, ROOT
from tiktoks.io import read_yaml
from tiktoks.maps import (
    draw_binary,
    draw_choropleth,
    join_codes,
    join_values,
    prepare_world,
    quantile_edges,
    read_geography,
    world_countries,
)
from tiktoks.post import Post
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import Theme, get_theme

CATALOG_PATH = GUESS_MAP_CATALOG_PATH
CATALOG_OUTPUT = POSTS_DIR / "guess-map"


def render_guess_map(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    """Render one post from a directory config."""
    config_path = Path(config_path)
    entry = read_yaml(config_path)
    entry.setdefault("slug", config_path.parent.name)
    override = entry.get("output_dir")
    # A relative path in a config means relative to the repo, not the shell's cwd.
    output_dir = (ROOT / override) if override else CATALOG_OUTPUT / entry["slug"]
    return _render(entry, output_dir, theme, base_dir=config_path.parent, config_path=config_path)


def render_catalog(
    catalog_path: Path | str | None = None,
    *,
    slug: str | None = None,
    theme: Theme | str | None = None,
    output_root: Path | None = None,
) -> list[Path]:
    """Render one entry, or every entry, from a catalog file."""
    catalog_path = Path(catalog_path or CATALOG_PATH)
    entries = catalog.load(catalog_path)
    if slug:
        if slug not in entries:
            raise KeyError(f"{slug!r} is not in {catalog_path}. Have: {', '.join(sorted(entries))}")
        chosen = [entries[slug]]
    else:
        chosen = list(entries.values())

    root = Path(output_root or CATALOG_OUTPUT)
    rendered: list[Path] = []
    for entry in chosen:
        rendered += _render(
            entry,
            root / entry["slug"],
            theme,
            base_dir=catalog_path.parent,
            config_path=catalog_path,
        )
    return rendered


def _resolve_data(entry: dict, base_dir: Path) -> tuple[pd.DataFrame, str, str]:
    """The value frame, its value column and the key to join it on."""
    if entry.get("fetch"):
        frame, column = catalog.resolve(entry, base_dir=base_dir)
        return frame, column, "iso3"
    frame = pd.read_csv(base_dir / entry["data"])
    return frame, entry["value_column"], entry.get("data_key", "name")


def _render(
    entry: dict,
    output_dir: Path,
    theme: Theme | str | None,
    *,
    base_dir: Path,
    config_path: Path,
) -> list[Path]:
    theme = get_theme(theme or entry.get("theme"))
    output_dir = Path(output_dir) / theme.name

    binary = entry.get("map_type") == "binary"
    values, column, key = _resolve_data(entry, base_dir)

    geography = read_geography(entry["geography"]) if entry.get("geography") else world_countries()
    if key == "iso3":
        # A members query returns only the members, so everything else is a real
        # zero rather than missing data.
        joined = join_codes(geography, values, value_column=column, fill=0 if binary else None)
    else:
        joined = join_values(geography, values, geo_key=entry.get("geo_key", "name"), data_key=key)
    view = prepare_world(joined, hide_antarctica=entry.get("hide_antarctica", True))

    bins = entry.get("bins", len(theme.sequential))
    difficulty = entry.get("difficulty", "medium")

    post = Post(
        slug=entry["slug"],
        format="guess-map",
        theme=theme,
        output_dir=output_dir,
        difficulty=difficulty,
        topic=entry.get("topic"),
        title=entry.get("answer"),
        caption=entry.get("caption"),
        hashtags=entry.get("hashtags", ["maps", "geography", "dataviz", "guessthemap"]),
        sources=[entry["source"]],
        config_path=config_path,
    )

    mystery = _mystery(entry, theme, difficulty)
    answer = _answer(entry, theme, difficulty)
    if not binary:
        edges = quantile_edges(view.base[column], bins)
        template = entry.get("legend_format", "{:,.0f}")
        answer.legend(
            list(theme.sequential[:bins]),
            [template.format(edges[0]), template.format(edges[-1])],
            no_data=view.base[column].isna().any(),
        )

    slot = shared_slot(mystery, answer)
    for kind, slide in (("mystery", mystery), ("answer", answer)):
        axes, aspect = slide.map_axes(slot=slot, data_aspect=view.aspect, bleed=True)
        if binary:
            draw_binary(
                axes,
                view,
                value_column=column,
                active_value=entry.get("active_value", 1),
                active_color=entry.get("active_color") or theme.highlight,
                theme=theme,
                aspect=aspect,
            )
        else:
            draw_choropleth(axes, view, value_column=column, theme=theme, aspect=aspect, bins=bins)
        post.add(slide, kind=kind, alt=_alt(entry, kind), title=entry.get("answer"))

    # A falsifiable challenge outpulls "what do you think?" in the comments.
    if entry.get("challenge"):
        post.add(_challenge(entry, theme, difficulty), kind="challenge", alt=entry["challenge"])

    post.finish()
    return post.paths


def _mystery(entry: dict, theme: Theme, difficulty: str) -> Slide:
    slide = Slide(
        theme,
        source=entry.get("mystery_source", "Source revealed on the next slide."),
        cue="Answer on the next slide",
        badge=difficulty,
        badge_color=theme.color_for(difficulty),
    )
    slide.kicker("Guess the map")
    slide.title(entry.get("prompt", "What does this map show?"), hero=True)
    slide.dek(entry.get("clue", ""))
    return slide


def _answer(entry: dict, theme: Theme, difficulty: str) -> Slide:
    slide = Slide(
        theme,
        source=entry["source"],
        badge=difficulty,
        badge_color=theme.color_for(difficulty),
    )
    slide.kicker("Answer")
    slide.title(entry["answer"])
    slide.dek(entry.get("answer_note", ""))
    return slide


def _challenge(entry: dict, theme: Theme, difficulty: str) -> Slide:
    slide = Slide(
        theme,
        cue="Drop it in the comments",
        badge=difficulty,
        badge_color=theme.color_for(difficulty),
    )
    slide.kicker("Your turn")
    slide.title(entry["challenge"])
    slide.dek(entry.get("challenge_note", ""))
    return slide


def _alt(entry: dict, kind: str) -> str:
    if kind == "mystery":
        return "An unlabeled world map with countries shaded. The subject is not named."
    note = entry.get("answer_note", "")
    return f"A world map. {entry['answer']}. {note}".strip()
