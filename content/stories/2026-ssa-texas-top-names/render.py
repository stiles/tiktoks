from pathlib import Path

import matplotlib.ticker as mticker
import pandas as pd

from tiktoks.charts import label_end, style_axes
from tiktoks.io import read_yaml
from tiktoks.paths import story_data, story_posts
from tiktoks.slides import Slide

HERE = Path(__file__).resolve().parent
SLUG = HERE.name
PROCESSED_DIR = story_data(SLUG) / "processed"

SEX_LABELS = {"F": "girl", "M": "boy"}


def render_name_chart(
    series: pd.DataFrame,
    *,
    title: str,
    dek: str,
    source: str,
    output: Path,
) -> None:
    latest = series.iloc[-1]
    slide = Slide(source=source)
    slide.kicker("baby names")
    slide.title(title)
    slide.dek(dek)

    axes = slide.chart_axes()
    theme = slide.theme
    axes.plot(series["year"], series["share_per_100k"], color=theme.highlight, linewidth=6)
    style_axes(axes, theme)
    axes.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}"))

    first, last = int(series["year"].min()), int(series["year"].max())
    axes.set_xlim(first, last + 42)
    axes.set_xticks(range(1900, last + 1, 25))
    label_end(
        axes,
        latest["year"],
        latest["share_per_100k"],
        f"{latest['share_per_100k']:.1f}\nper 100k",
        theme,
        size=26,
    )
    slide.save(output)


def top_name_copy(
    *,
    name: str,
    rank: int,
    sex: str,
    births: int,
    year: int,
    state_label: str,
) -> tuple[str, str]:
    label = SEX_LABELS[sex]
    return (
        f"{name} is the #{rank} {label} name in {state_label}",
        f"{births:,} {state_label} babies were named {name} in {year}.",
    )


def render_group(
    group: pd.DataFrame,
    *,
    series: pd.DataFrame,
    direction: str,
    year: int,
    state_label: str,
    source: str,
    out_dir: Path,
    prefix: str,
) -> None:
    ordered = group.sort_values("rank", ascending=False)
    for _, row in ordered.iterrows():
        title, dek = top_name_copy(
            name=row["name"],
            rank=int(row["rank"]),
            sex=row["sex"],
            births=int(row["births"]),
            year=year,
            state_label=state_label,
        )
        subset = series[(series["name"] == row["name"]) & (series["sex"] == row["sex"])]
        render_name_chart(
            subset,
            title=title,
            dek=dek,
            source=source,
            output=out_dir / f"{prefix}-{int(row['rank']):02d}.png",
        )


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    girls = pd.read_csv(PROCESSED_DIR / "girls.csv")
    boys = pd.read_csv(PROCESSED_DIR / "boys.csv")
    series = pd.read_csv(PROCESSED_DIR / "name_series.csv")
    out_dir = story_posts(SLUG)
    out_dir.mkdir(parents=True, exist_ok=True)

    cover = Slide(source=config["source"])
    cover.kicker("baby names")
    cover.title(config["title"])
    cover.dek(config["dek"])
    cover.save(out_dir / "ssa-texas-top-names-00-cover.png")

    render_group(
        girls,
        series=series,
        direction="girls",
        year=config["year"],
        state_label=config["state_label"],
        source=config["source"],
        out_dir=out_dir,
        prefix="ssa-texas-top-names-girls",
    )
    render_group(
        boys,
        series=series,
        direction="boys",
        year=config["year"],
        state_label=config["state_label"],
        source=config["source"],
        out_dir=out_dir,
        prefix="ssa-texas-top-names-boys",
    )

    print(f"Wrote 11 slides to {out_dir}")


if __name__ == "__main__":
    main()
