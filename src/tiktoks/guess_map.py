from pathlib import Path

import pandas as pd

from tiktoks.io import read_yaml
from tiktoks.maps import (
    draw_binary,
    draw_choropleth,
    join_values,
    prepare_world,
    quantile_edges,
    read_geography,
    world_countries,
)
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import Theme, get_theme


def render_guess_map(config_path: Path | str, theme: Theme | str | None = None) -> list[Path]:
    config_path = Path(config_path)
    config = read_yaml(config_path)
    theme = get_theme(theme or config.get("theme"))
    output_dir = config_path.parent / config.get("output_dir", "output") / theme.name

    values = pd.read_csv(config_path.parent / config["data"])
    geography = (
        read_geography(config["geography"]) if config.get("geography") else world_countries()
    )
    joined = join_values(
        geography,
        values,
        geo_key=config.get("geo_key", "name"),
        data_key=config.get("data_key", "name"),
    )
    view = prepare_world(joined, hide_antarctica=config.get("hide_antarctica", True))

    binary = config.get("map_type") == "binary"
    column = config["value_column"]
    bins = config.get("bins", len(theme.sequential))

    mystery = _mystery(config, theme)
    answer = _answer(config, theme)
    if not binary:
        edges = quantile_edges(view.base[column], bins)
        template = config.get("legend_format", "{:,.0f}")
        answer.legend(
            list(theme.sequential[:bins]),
            [template.format(edges[0]), template.format(edges[-1])],
            no_data=view.base[column].isna().any(),
        )

    slot = shared_slot(mystery, answer)
    rendered = []
    for name, slide in (("01-mystery", mystery), ("02-answer", answer)):
        axes = slide.map_axes(slot=slot, data_aspect=view.aspect, bleed=True)
        if binary:
            draw_binary(
                axes,
                view,
                value_column=column,
                active_value=config.get("active_value", 1),
                active_color=config.get("active_color") or theme.highlight,
                theme=theme,
                aspect=slide.map_aspect,
            )
        else:
            draw_choropleth(
                axes,
                view,
                value_column=column,
                theme=theme,
                aspect=slide.map_aspect,
                bins=config.get("bins"),
            )
        rendered.append(slide.save(output_dir / f"guess-map-{name}.png"))
    return rendered


def _mystery(config: dict, theme: Theme) -> Slide:
    difficulty = config.get("difficulty", "medium")
    slide = Slide(
        theme,
        source=config.get("mystery_source", "Source revealed on the next slide."),
        cue="Answer on the next slide",
        badge=difficulty,
        badge_color=theme.color_for(difficulty),
    )
    slide.kicker("Guess the map")
    slide.title(config.get("prompt", "What does this map show?"), hero=True)
    slide.dek(config.get("clue", ""))
    return slide


def _answer(config: dict, theme: Theme) -> Slide:
    difficulty = config.get("difficulty", "medium")
    slide = Slide(
        theme,
        source=config["source"],
        badge=difficulty,
        badge_color=theme.color_for(difficulty),
    )
    slide.kicker("Answer")
    slide.title(config["answer"])
    slide.dek(config.get("answer_note", ""))
    return slide
