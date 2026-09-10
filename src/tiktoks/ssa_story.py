from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import matplotlib.ticker as mticker
import pandas as pd
import requests

from tiktoks.charts import label_end, style_axes
from tiktoks.io import read_yaml
from tiktoks.paths import repo_root, story_data, story_posts
from tiktoks.post import Post
from tiktoks.slides import Slide
from tiktoks.ssa_names import load_names, name_series
from tiktoks.style import get_theme

# ssa.gov returns 403 to the default requests user agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def _story_config(story_dir: Path) -> dict:
    return read_yaml(Path(story_dir) / "story.yaml")


def _raw_dir(config: dict, story_dir: Path) -> Path:
    if config.get("raw_dir"):
        return repo_root() / config["raw_dir"]
    return story_data(config.get("raw_slug", Path(story_dir).name)) / "raw"


def _processed_dir(story_dir: Path) -> Path:
    return story_data(Path(story_dir).name) / "processed"


def _series_path(story_dir: Path) -> Path:
    return _processed_dir(story_dir) / "name_series.csv"


def ensure_ssa_raw_data(story_dir: Path) -> Path:
    config = _story_config(story_dir)
    raw_dir = _raw_dir(config, story_dir)
    if list(raw_dir.glob("yob*.txt")):
        return raw_dir

    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "ssa_names.zip"
    response = requests.get(config["source_url"], headers=HEADERS, timeout=60)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with ZipFile(zip_path) as archive:
        for member in archive.namelist():
            if member.startswith("yob") and member.endswith(".txt"):
                archive.extract(member, raw_dir)
    return raw_dir


def process_single_name_story(story_dir: Path) -> Path:
    config = _story_config(story_dir)
    raw_dir = ensure_ssa_raw_data(story_dir)
    names = load_names(raw_dir)
    selected = name_series(names, config["name"])

    processed_dir = _processed_dir(story_dir)
    processed_dir.mkdir(parents=True, exist_ok=True)
    path = processed_dir / "name_series.csv"
    selected.to_csv(path, index=False)
    return path


def _percent_off_peak(series: pd.DataFrame) -> float:
    peak = float(series["share_per_100k"].max())
    latest = float(series.iloc[-1]["share_per_100k"])
    return (1 - latest / peak) * 100


def _series_point(series: pd.DataFrame, year: int) -> pd.Series | None:
    matched = series[series["year"] == year]
    if matched.empty:
        return None
    return matched.iloc[0]


def _base_chart(slide: Slide, series: pd.DataFrame):
    axes = slide.chart_axes()
    theme = slide.theme
    axes.plot(
        series["year"],
        series["share_per_100k"],
        color=theme.border,
        linewidth=4,
        alpha=0.55,
        zorder=1,
    )
    style_axes(axes, theme)
    axes.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}"))
    first, last = int(series["year"].min()), int(series["year"].max())
    axes.set_xlim(first, last + 34)
    axes.set_xticks(range(1900, last + 1, 25))
    return axes, theme


def _render_progress_chart(
    *,
    title: str,
    dek: str,
    source: str,
    series: pd.DataFrame,
    stop_year: int,
    label: str,
    color: str | None = None,
) -> Slide:
    slide = Slide(source=source)
    slide.kicker("baby names")
    slide.title(title)
    slide.dek(dek)

    axes, theme = _base_chart(slide, series)
    color = color or theme.highlight
    active = series[series["year"] <= stop_year]
    axes.plot(active["year"], active["share_per_100k"], color=color, linewidth=6, zorder=2)
    latest = active.iloc[-1]
    label_end(axes, latest["year"], latest["share_per_100k"], label, theme, color=color, size=24)
    return slide


def _render_decline_compare(
    *,
    title: str,
    dek: str,
    source: str,
    series: pd.DataFrame,
    name: str,
) -> Slide:
    slide = Slide(source=source, cue="Comment a name to try next")
    slide.kicker("baby names")
    slide.title(title)
    slide.dek(dek)

    axes = slide.chart_axes()
    theme = slide.theme
    indexed = series.assign(index=series["share_per_100k"] / series["share_per_100k"].max() * 100)
    axes.plot(indexed["year"], indexed["index"], color=theme.highlight, linewidth=6)
    style_axes(axes, theme)
    axes.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}"))
    axes.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}"))
    last = int(indexed["year"].max())
    axes.set_xlim(1880, last + 34)
    axes.set_xticks(range(1900, last + 1, 25))
    axes.set_ylim(0, 105)
    label_end(
        axes,
        indexed.iloc[-1]["year"],
        indexed.iloc[-1]["index"],
        name,
        theme,
        color=theme.highlight,
        size=24,
        offset=0.018,
    )
    return slide


def render_single_name_story(story_dir: Path) -> list[Path]:
    story_dir = Path(story_dir)
    config = _story_config(story_dir)
    series_path = _series_path(story_dir)
    if not series_path.exists():
        process_single_name_story(story_dir)
    series = pd.read_csv(series_path)

    peak = series.loc[series["share_per_100k"].idxmax()]
    latest = series.iloc[-1]
    decline = _percent_off_peak(series)

    post = Post(
        slug=config["slug"],
        format="story",
        theme=get_theme("night"),
        output_dir=story_posts(config["slug"]),
        topic="baby names",
        title=config["title"],
        caption=config.get("caption"),
        hashtags=config.get("hashtags", ["babynames", "ssa", "data", "names"]),
        sources=[config["source"]],
        config_path=story_dir / "story.yaml",
    )

    cover = Slide(source=config["source"])
    cover.kicker("baby names")
    cover.title(config["title"])
    cover.dek(config["dek"])
    post.add(
        cover,
        kind="cover",
        alt=f"A title slide about the baby name {config['name']}.",
        title=config["title"],
    )

    peak_slide = _render_progress_chart(
        title=config["peak_title"],
        dek=(
            f"In {int(peak['year'])}, {int(peak['births']):,} US babies "
            f"were named {config['name']}. "
            f"That was {peak['share_per_100k']:.0f} per 100,000 births."
        ),
        source=config["source"],
        series=series,
        stop_year=int(peak["year"]),
        label=f"Peak\n{int(peak['year'])}",
    )
    post.add(
        peak_slide,
        kind="story",
        alt=(
            f"A line chart of the baby name {config['name']}, "
            f"rising to its peak year {int(peak['year'])}."
        ),
        title=config["peak_title"],
    )

    midyear = config.get("midyear")
    if midyear:
        point = _series_point(series, int(midyear))
        if point is not None:
            mid_slide = _render_progress_chart(
                title=config["mid_title"],
                dek=config["mid_dek"].format(
                    name=config["name"],
                    year=int(point["year"]),
                    births=int(point["births"]),
                    share=point["share_per_100k"],
                ),
                source=config["source"],
                series=series,
                stop_year=int(point["year"]),
                label=f"{int(point['year'])}\n{point['share_per_100k']:.1f}",
                color=get_theme("night").accent,
            )
            post.add(
                mid_slide,
                kind="story",
                alt=(
                    f"A line chart of the baby name {config['name']} "
                    f"through {int(point['year'])}."
                ),
                title=config["mid_title"],
            )

    decline_slide = _render_progress_chart(
        title=config["decline_title"],
        dek=(
            f"By {int(latest['year'])}, it was down to {int(latest['births']):,} births, "
            f"about {decline:.0f}% below its peak share."
        ),
        source=config["source"],
        series=series,
        stop_year=int(latest["year"]),
        label=f"{int(latest['year'])}\n{latest['share_per_100k']:.1f}",
    )
    post.add(
        decline_slide,
        kind="story",
        alt=(
            f"A line chart of the baby name {config['name']}, extending through "
            f"{int(latest['year'])} after a long decline."
        ),
        title=config["decline_title"],
    )

    compare = _render_decline_compare(
        title=config["compare_title"],
        dek=config["compare_dek"].format(
            name=config["name"],
            year=int(latest["year"]),
            births=int(latest["births"]),
            decline=decline,
        ),
        source=config["source"],
        series=series,
        name=config["name"],
    )
    post.add(
        compare,
        kind="story",
        alt=(
            f"A normalized line chart showing how far the baby name "
            f"{config['name']} is below peak."
        ),
        title=config["compare_title"],
    )

    outro = Slide(source=config["source"], cue="Comment a name to try next")
    outro.kicker("baby names")
    outro.title(config.get("outro_title", "Should I chart your name too?"))
    outro.dek(
        config.get(
            "outro_dek",
            "Drop a first name in the comments and I can pull the SSA line for it.",
        )
    )
    post.add(
        outro,
        kind="outro",
        alt=(
            f"A closing slide asking viewers to suggest the next baby name "
            f"after {config['name']}."
        ),
        title=config.get("outro_title", "Should I chart your name too?"),
    )

    post.finish()
    return post.paths
