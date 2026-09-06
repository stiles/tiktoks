"""Render one test set of slides in every theme, then tile them for review.

    uv run python scripts/style_lab.py

Writes slides to output/style-lab/<theme>/ and contact sheets to
output/style-lab/sheet-<theme>.png. The set covers the cases that break layouts:
a long title, a huge high-latitude country, a microstate and a world map.
"""

from pathlib import Path

import pandas as pd

from tiktoks.export import contact_sheet
from tiktoks.maps import (
    draw_binary,
    draw_choropleth,
    draw_highlight,
    join_values,
    prepare_country,
    prepare_world,
    world_countries,
)
from tiktoks.slides import Slide, shared_slot
from tiktoks.style import THEMES, Theme

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review" / "style-lab"
NATO = ROOT / "content" / "guess-map-csv-example"
BOUNDARIES = "Boundaries: Natural Earth"


def country_pair(theme: Theme, countries, name: str, fact: str, difficulty: str) -> list[Slide]:
    color = theme.color_for(difficulty)
    prompt = Slide(
        theme, source=BOUNDARIES, cue="Swipe for the answer", badge=difficulty, badge_color=color
    )
    prompt.kicker("Name that country")
    prompt.title("Which country is highlighted?")

    answer = Slide(theme, source=BOUNDARIES, badge=difficulty, badge_color=color)
    answer.kicker("Answer")
    answer.title(name)
    answer.dek(fact)

    view = prepare_country(countries, [name])
    slot = shared_slot(prompt, answer)
    for slide in (prompt, answer):
        draw_highlight(
            slide.map_axes(slot=slot)[0], view, theme=theme, aspect=slide.map_aspect, color=color
        )
    return [prompt, answer]


def nato_mystery(theme: Theme, geography) -> Slide:
    slide = Slide(
        theme,
        source="Source revealed on the next slide.",
        cue="Answer on the next slide",
        badge="easy",
        badge_color=theme.color_for("easy"),
    )
    slide.kicker("Guess the map")
    slide.title("What do these countries have in common?", hero=True)
    view = prepare_world(geography)
    axes, aspect = slide.map_axes(data_aspect=view.aspect, bleed=True)
    draw_binary(axes, view, value_column="nato_member", theme=theme, aspect=aspect)
    return slide


def gdp_choropleth(theme: Theme, geography) -> Slide:
    slide = Slide(
        theme,
        source="Source: World Bank, 2023; Natural Earth boundaries.",
        badge="medium",
        badge_color=theme.color_for("medium"),
    )
    slide.kicker("Answer")
    slide.title("GDP per capita")
    slide.dek("Purchasing power parity, current international dollars.")
    slide.legend(list(theme.sequential), ["$400", "$140,000"], no_data=True)
    view = prepare_world(geography)
    axes, aspect = slide.map_axes(data_aspect=view.aspect, bleed=True)
    draw_choropleth(axes, view, value_column="gdp_pc", theme=theme, aspect=aspect)
    return slide


def main() -> None:
    countries = world_countries()
    nato = join_values(countries, pd.read_csv(NATO / "data.csv"), geo_key="name", data_key="name")

    # Stand-in values so the choropleth has a real distribution to bin.
    spread = pd.Series(range(len(countries)), index=countries.index)
    gdp = countries.copy()
    gdp["gdp_pc"] = (spread * 617 % 139_600 + 400).where(spread % 11 != 0)

    for name, theme in THEMES.items():
        italy = country_pair(
            theme,
            countries,
            "Italy",
            "The boot-shaped peninsula reaches into the Mediterranean Sea.",
            "easy",
        )
        lesotho = country_pair(
            theme,
            countries,
            "Lesotho",
            "A landlocked kingdom entirely surrounded by South Africa.",
            "expert",
        )
        canada = country_pair(
            theme, countries, "Canada", "It has the world's longest coastline.", "easy"
        )
        slides = [
            ("01-italy-prompt", italy[0]),
            ("02-italy-answer", italy[1]),
            ("03-canada-prompt", canada[0]),
            ("04-lesotho-prompt", lesotho[0]),
            ("05-nato-mystery", nato_mystery(theme, nato)),
            ("06-gdp-choropleth", gdp_choropleth(theme, gdp)),
        ]
        paths = [slide.save(OUT / name / f"{stem}.png") for stem, slide in slides]
        sheet = contact_sheet(paths, OUT / f"sheet-{name}.png", columns=3)
        print(f"{name}: {len(paths)} slides -> {sheet}")


if __name__ == "__main__":
    main()
