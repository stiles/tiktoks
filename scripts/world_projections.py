"""Compare world projections for a portrait slide.

    uv run python scripts/world_projections.py

Equal Earth is 2.25:1 once Antarctica is dropped, so it fills less than half of a
1080x1920 slide. Bonne is also equal-area but much taller. This renders the same
guess-the-map slide in each so the tradeoff is visible.
"""

from pathlib import Path

import pandas as pd

from tiktoks.export import contact_sheet
from tiktoks.maps import (
    MapView,
    draw_binary,
    drop_antarctica,
    join_values,
    pad_bounds,
    world_countries,
)
from tiktoks.slides import Slide
from tiktoks.style import PAPER

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "review" / "world-projections"

OPTIONS = {
    "eqearth": "+proj=eqearth +lon_0=10",
    "bonne-30": "+proj=bonne +lat_1=30 +lon_0=10",
    "bonne-45": "+proj=bonne +lat_1=45 +lon_0=10",
    "werner": "+proj=bonne +lat_1=89.9 +lon_0=10",
}


def main() -> None:
    countries = world_countries()
    nato = join_values(
        countries,
        pd.read_csv(ROOT / "content/guess-map-csv-example/data.csv"),
        geo_key="name",
        data_key="name",
    )
    trimmed = drop_antarctica(nato)

    paths = []
    for name, proj in OPTIONS.items():
        frame = trimmed.to_crs(f"{proj} +datum=WGS84 +units=m +no_defs")
        view = MapView(frame, tuple(pad_bounds(frame.total_bounds, 0.01)))

        slide = Slide(
            PAPER,
            source=f"Projection: {name}. Boundaries: Natural Earth.",
            cue="Answer on the next slide",
            badge="easy",
            badge_color=PAPER.color_for("easy"),
        )
        slide.kicker("Guess the map")
        slide.title("What do these countries have in common?")
        axes, aspect = slide.map_axes(data_aspect=view.aspect, bleed=True)
        draw_binary(axes, view, value_column="nato_member", theme=PAPER, aspect=aspect)
        paths.append(slide.save(OUT / f"{name}.png"))

    print(contact_sheet(paths, OUT / "sheet.png", columns=4))


if __name__ == "__main__":
    main()
