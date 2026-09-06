from pathlib import Path

import pandas as pd

from tiktoks import catalog, palettes
from tiktoks.config import GUESS_MAP_CATALOG_PATH, POSTS_DIR, ROOT
from tiktoks.io import read_yaml
from tiktoks.maps import (
    classification_edges,
    derive_value,
    draw_binary,
    draw_boundaries,
    draw_choropleth,
    draw_points,
    join_codes,
    join_values,
    prepare_region,
    prepare_world,
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
    geography = read_geography(entry["geography"]) if entry.get("geography") else world_countries()
    overlay = entry.get("boundary_overlay")
    boundaries = read_geography(overlay) if overlay else None
    map_kind = entry.get("map_kind", "polygons")
    regional = entry.get("region_bounds")
    if map_kind == "points":
        points = read_geography(entry["points"])
        view = prepare_region(geography, bounds=regional) if regional else prepare_world(geography)
        column = None
    elif value := entry.get("value"):
        column = value.get("column", "value")
        options = {key: item for key, item in value.items() if key != "column"}
        joined = derive_value(geography, column=column, **options)
        view = prepare_region(joined, bounds=regional) if regional else prepare_world(joined)
    else:
        values, column, key = _resolve_data(entry, base_dir)
        if key == "iso3":
            # A members query returns only the members, so everything else is a real
            # zero rather than missing data.
            joined = join_codes(geography, values, value_column=column, fill=0 if binary else None)
        else:
            joined = join_values(
                geography, values, geo_key=entry.get("geo_key", "name"), data_key=key
            )
        view = (
            prepare_region(joined, bounds=regional)
            if regional
            else prepare_world(joined, hide_antarctica=entry.get("hide_antarctica", True))
        )

    bins = entry.get("bins", 6)
    # One hue, light for low and dark for high. The theme ramps run dark to light,
    # which reads as darker meaning less.
    colors = palettes.sequential(entry.get("palette"), bins)
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
    if not binary and map_kind != "points":
        scheme = entry.get("scheme", "quantiles")
        edges = classification_edges(view.base[column], bins, scheme)
        template = entry.get("legend_format", "{:,.0f}")
        answer.legend(
            colors,
            [template.format(edges[0]), template.format(edges[-1])],
            no_data=view.base[column].isna().any(),
        )

    slot = shared_slot(mystery, answer)
    for kind, slide in (("mystery", mystery), ("answer", answer)):
        axes, aspect = slide.map_axes(slot=slot, data_aspect=view.aspect, bleed=True)
        if map_kind == "points":
            draw_points(
                axes,
                view,
                points,
                theme=theme,
                aspect=aspect,
                color=entry.get("point_color"),
                size=entry.get("point_size", 20),
            )
        elif binary:
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
            draw_choropleth(
                axes,
                view,
                value_column=column,
                theme=theme,
                aspect=aspect,
                colors=colors,
                scheme=entry.get("scheme", "quantiles"),
            )
            if boundaries is not None:
                draw_boundaries(
                    axes,
                    view,
                    boundaries,
                    color=entry.get("boundary_color", theme.muted),
                    width=entry.get("boundary_width", 1.2),
                )
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
    # Not a hero title. The hero size was chosen when a world map filled less than
    # half the frame; it is what was keeping the map small.
    slide.title(entry.get("prompt", "What does this map show?"), max_lines=2)
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
    # Two lines, so a long answer shrinks instead of eating the map's space.
    slide.title(entry["answer"], max_lines=2)
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
        return entry.get(
            "mystery_alt",
            "An unlabeled world map with countries shaded. The subject is not named.",
        )
    note = entry.get("answer_note", "")
    return entry.get("answer_alt", f"A map. {entry['answer']}. {note}".strip())
