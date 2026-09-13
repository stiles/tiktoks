from __future__ import annotations

import geopandas as gpd
import json
import subprocess
from pathlib import Path

from shapely.geometry import box

from tiktoks.maps import frame_axes, prepare_world_projection, world_countries
from tiktoks.paths import ensure_dir, story_posts
from tiktoks.slides import Slide
from tiktoks.style import get_theme

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
OUT_DIR = story_posts(SLUG) / "meme"
FPS = 30
TOTAL_SECONDS = 10.0

PROJECTIONS = {
    "equal-earth": {
        "label": "EQUAL EARTH",
        "crs": "+proj=eqearth +lon_0=0 +datum=WGS84 +units=m +no_defs",
        "zoom": 1.12,
        "trim": 0,
        "shift_x": -0.10,
    },
    "mercator": {
        "label": "MERCATOR",
        "crs": "+proj=merc +lon_0=0 +datum=WGS84 +units=m +no_defs",
        "zoom": 1.02,
        "trim": 0,
        "shift_x": -0.08,
    },
}

TIMING = {
    "mercator_hold_start": 1.10,
    "to_equal_earth": 1.55,
    "equal_hold": 2.45,
    "to_mercator": 1.35,
    "mercator_hold_end": 3.55,
}


def _mercator_source(countries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Mercator blows up toward the poles. Clipping to inhabited latitudes keeps
    # Greenland dramatic without turning the Arctic into a broken slab.
    return countries.clip(box(-180, -82, 180, 82))


def _shift_view_x(view, amount: float):
    min_x, min_y, max_x, max_y = view.bounds
    width = max_x - min_x
    offset = width * amount
    view.bounds = (min_x + offset, min_y, max_x + offset, max_y)
    return view


def _draw_state(ax, view, theme, *, aspect: float, zoom: float) -> None:
    ax.set_facecolor(theme.water)
    view.base.plot(
        ax=ax,
        color=theme.highlight,
        edgecolor="#d7e7ff",
        linewidth=0.7,
    )

    bounds = view.bounds
    if zoom != 1.0:
        min_x, min_y, max_x, max_y = bounds
        center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        half_w = (max_x - min_x) / 2 / zoom
        half_h = (max_y - min_y) / 2 / zoom
        bounds = (center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)
    frame_axes(ax, bounds, aspect)


def render_state(name: str, countries: gpd.GeoDataFrame) -> Path:
    theme = get_theme("night")
    spec = PROJECTIONS[name]
    source = _mercator_source(countries) if name == "mercator" else countries
    view = prepare_world_projection(source, spec["crs"], trim=spec["trim"])
    view = _shift_view_x(view, spec.get("shift_x", 0.0))
    slide = Slide(theme, safe_area=False)
    axes, aspect = slide.backdrop_axes()
    _draw_state(axes, view, theme, aspect=aspect, zoom=spec["zoom"])
    slide.scrim(alpha=0.03, color=theme.background)
    slide.canvas.text(
        540,
        1538,
        spec["label"],
        color=theme.text,
        fontsize=38,
        fontweight="bold",
        fontfamily=theme.body_font,
        ha="center",
        va="center",
        alpha=0.92,
        zorder=4,
    )
    slide.canvas.text(
        540,
        1596,
        "Same world. Different projection.",
        color=theme.muted,
        fontsize=22,
        fontfamily=theme.body_font,
        ha="center",
        va="center",
        alpha=0.95,
        zorder=4,
    )
    return slide.save(OUT_DIR / f"{name}.png")


def render_video() -> Path:
    ensure_dir(OUT_DIR)
    countries = world_countries()
    paths = {name: render_state(name, countries) for name in PROJECTIONS}

    beat_sheet = {
        "fps": FPS,
        "total_seconds": TOTAL_SECONDS,
        "timing": TIMING,
        "notes": [
            "Start on Mercator for the setup.",
            "Crossfade into Equal Earth on 'Why would I deceive you?'",
            "Hold on Equal Earth for the pause.",
            "Crossfade back to Mercator on 'There's no reason...'",
            "Hold on Mercator to finish the 10-second sound cleanly.",
        ],
    }
    (OUT_DIR / "beats.json").write_text(json.dumps(beat_sheet, indent=2) + "\n", encoding="utf-8")

    output = OUT_DIR / f"{SLUG}-meme-10s.mp4"
    fade_back_offset = TIMING["mercator_hold_start"] + TIMING["to_equal_earth"] + TIMING["equal_hold"]
    equal_earth_span = TIMING["to_equal_earth"] + TIMING["equal_hold"] + TIMING["to_mercator"]
    ending_span = TIMING["to_mercator"] + TIMING["mercator_hold_end"]
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-t",
        f"{TOTAL_SECONDS:.3f}",
        "-i",
        str(paths["mercator"]),
        "-loop",
        "1",
        "-t",
        f"{TOTAL_SECONDS:.3f}",
        "-i",
        str(paths["equal-earth"]),
        "-filter_complex",
        (
            f"[0:v]trim=duration={TOTAL_SECONDS:.3f},setpts=PTS-STARTPTS[merc_base];"
            f"[0:v]trim=duration={ending_span:.3f},setpts=PTS-STARTPTS[merc_end];"
            f"[1:v]trim=duration={equal_earth_span:.3f},setpts=PTS-STARTPTS[eqearth];"
            "[merc_base][eqearth]xfade=transition=fade:duration="
            f"{TIMING['to_equal_earth']:.3f}:offset={TIMING['mercator_hold_start']:.3f}[v1];"
            f"[v1][merc_end]xfade=transition=fade:duration={TIMING['to_mercator']:.3f}:"
            f"offset={fade_back_offset:.3f},format=yuv420p[v]"
        ),
        "-map",
        "[v]",
        "-r",
        str(FPS),
        "-frames:v",
        str(int(FPS * TOTAL_SECONDS)),
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().splitlines()
        tail = "\n".join(detail[-12:]) if detail else "no ffmpeg output"
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
    return output


def main() -> None:
    output = render_video()
    print(output)


if __name__ == "__main__":
    main()
