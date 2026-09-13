from __future__ import annotations

from pathlib import Path

from tiktoks.io import read_yaml
from tiktoks.maps import draw_backdrop, prepare_world_projection, world_countries
from tiktoks.paths import story_posts
from tiktoks.post import Post
from tiktoks.slides import Slide
from tiktoks.style import get_theme

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "story.yaml"

PROJECTIONS = {
    "mercator": {
        "label": "Mercator",
        "crs": "EPSG:3395",
        "zoom": 1.0,
    },
    "equal-earth": {
        "label": "Equal Earth",
        "crs": "+proj=eqearth +lon_0=0 +datum=WGS84 +units=m +no_defs",
        "zoom": 1.0,
    },
}

CAROUSEL_SLIDES = [
    {
        "kind": "cover",
        "mode": "cover",
        "projection": "equal-earth",
        "title": "Mercator vs. Equal Earth",
        "dek": "The world map you know best is not the best one for comparing size.",
        "cue": "Swipe through the case",
    },
    {
        "kind": "story",
        "projection": "mercator",
        "kicker": "Map projections · Mercator",
        "title": "Mercator is the familiar one.",
        "dek": "It became the default for navigation and then stayed familiar in classrooms, news graphics and web maps.",
    },
    {
        "kind": "story",
        "projection": "mercator",
        "kicker": "Map projections · Mercator",
        "title": "Its distortion gets worse away from the equator.",
        "dek": "That is why Greenland, Europe and northern Canada start reading larger than they should.",
    },
    {
        "kind": "story",
        "projection": "equal-earth",
        "kicker": "Map projections · Equal Earth",
        "title": "Equal Earth gives a calmer size comparison.",
        "dek": "The coastlines bend more, but the land areas read much closer to their actual proportions.",
    },
    {
        "kind": "story",
        "projection": "equal-earth",
        "kicker": "Map projections · Equal Earth",
        "title": "That trade usually works better for explainers.",
        "dek": "If the question is who is bigger, smaller or comparable, this is the cleaner frame.",
    },
    {
        "kind": "challenge",
        "projection": "equal-earth",
        "kicker": "Pick the lie that fits the job",
        "title": "Mercator is useful. It is just not neutral.",
        "dek": "Use it for bearings and slippy maps. Reach for Equal Earth when the audience is comparing the world.",
        "cue": "Comment which one you would post",
    },
]

SHUFFLE_SLIDES = [
    {
        "kind": "cover",
        "mode": "cover",
        "projection": "equal-earth",
        "title": 'Mercator: "Why would I deceive you?"',
        "dek": "Cartography edition.",
        "cue": "Wait for the reveal",
    },
    {
        "kind": "mystery",
        "projection": "mercator",
        "kicker": "The setup · Mercator",
        "title": '"Why would I deceive you?"',
        "dek": "Mercator, seconds before another polar country gets inflated.",
    },
    {
        "kind": "answer",
        "projection": "mercator",
        "kicker": "The problem · Mercator",
        "title": "Because this map stretches the high latitudes.",
        "dek": "The farther you move from the equator, the stranger the size comparison gets.",
    },
    {
        "kind": "prompt",
        "projection": "equal-earth",
        "kicker": "The reveal · Equal Earth",
        "title": "There is a less slippery option.",
        "dek": "Same planet. Cleaner size comparison.",
    },
    {
        "kind": "answer",
        "projection": "equal-earth",
        "kicker": "The reveal · Equal Earth",
        "title": "Equal Earth is the better comparison frame.",
        "dek": "It gives up some familiar shape so the area story reads more honestly at a glance.",
    },
    {
        "kind": "challenge",
        "projection": "equal-earth",
        "kicker": "The takeaway",
        "title": "Use the lie that matches the job.",
        "dek": "Navigation and web tiles: Mercator. World comparison graphics: Equal Earth.",
        "cue": "Post the one that fits your story",
    },
]


def _view_cache(countries) -> dict[str, object]:
    return {
        key: prepare_world_projection(countries, spec["crs"])
        for key, spec in PROJECTIONS.items()
    }


def _cover_slide(theme, spec: dict, view, index: int, total: int, source: str) -> Slide:
    slide = Slide(theme, source=source, badge=f"{index}/{total}")
    axes, aspect = slide.backdrop_axes()
    draw_backdrop(axes, view, theme=theme, aspect=aspect, zoom=1.75)
    slide.scrim(0.42 if theme.name == "paper" else 0.5)
    slide.centered_stack(
        [
            {
                "text": spec["title"],
                "size": int(theme.title_size * 1.25),
                "min_size": theme.title_min_size,
                "max_lines": 4,
                "font": theme.title_font,
                "weight": theme.title_weight,
                "leading": theme.title_leading,
                "color": theme.text,
                "gap_after": 36,
                "kind": "cover title",
            },
            {
                "text": spec["dek"],
                "size": 30,
                "min_size": 26,
                "max_lines": 4,
                "font": theme.body_font,
                "weight": "normal",
                "leading": theme.dek_leading,
                "color": theme.muted,
                "gap_after": 42,
                "kind": "cover dek",
            },
            {
                "text": spec["cue"],
                "size": 30,
                "font": theme.body_font,
                "weight": "bold",
                "leading": 1.1,
                "color": theme.accent,
                "kind": "cover cue",
            },
        ]
    )
    return slide


def _projection_slide(theme, spec: dict, view, projection_label: str, badge: str, source: str) -> Slide:
    slide = Slide(
        theme,
        source=source,
        cue=spec.get("cue"),
        badge=badge,
        badge_color=theme.accent,
    )
    slide.kicker(spec["kicker"])
    slide.title(spec["title"])
    slide.dek(spec["dek"])
    axes, aspect = slide.map_axes(
        data_aspect=view.aspect,
        slot=slide.content_slot(),
        bleed=True,
        min_height=0,
    )
    draw_backdrop(axes, view, theme=theme, aspect=aspect, zoom=PROJECTIONS[spec["projection"]]["zoom"])
    slide.canvas.text(
        slide.left,
        slide.height - 520,
        projection_label.upper(),
        color=theme.text,
        fontsize=24,
        fontweight="bold",
        fontfamily=theme.body_font,
        ha="left",
        va="top",
        zorder=4,
    )
    return slide


def _build_post(config: dict, name: str, slides: list[dict]) -> list[Path]:
    theme = get_theme(config.get("theme"))
    countries = world_countries()
    views = _view_cache(countries)
    output_dir = story_posts(config["slug"]) / name
    caption_key = "caption_video" if name == "shuffle" else f"caption_{name}"
    post = Post(
        slug=f"{config['slug']}-{name}",
        format="story",
        theme=theme,
        output_dir=output_dir,
        topic="map projections",
        title=slides[0]["title"],
        caption=config[caption_key],
        hashtags=config.get("hashtags", []),
        sources=[config["source"]],
        config_path=CONFIG_PATH,
    )

    total = len(slides)
    for index, spec in enumerate(slides, start=1):
        view = views[spec["projection"]]
        if spec.get("mode") == "cover":
            slide = _cover_slide(theme, spec, view, index, total, config["source"])
        else:
            slide = _projection_slide(
                theme,
                spec,
                view,
                PROJECTIONS[spec["projection"]]["label"],
                f"{index}/{total}",
                config["source"],
            )
        post.add(
            slide,
            kind=spec["kind"],
            alt=(
                f"A world map in the {PROJECTIONS[spec['projection']]['label']} projection. "
                f"{spec['title']}"
            ),
            title=spec["title"],
        )
    post.finish()
    return post.paths


def main() -> None:
    config = read_yaml(CONFIG_PATH)
    built = {
        "carousel": _build_post(config, "carousel", CAROUSEL_SLIDES),
        "shuffle": _build_post(config, "shuffle", SHUFFLE_SLIDES),
    }
    for name, paths in built.items():
        print(f"{name}: {len(paths)} slides -> {paths[0].parent}")


if __name__ == "__main__":
    main()
