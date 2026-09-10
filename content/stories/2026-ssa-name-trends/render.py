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


def rising_copy(name: str, share_change: float) -> tuple[str, str]:
    return (
        f"{name} is one of the fastest-rising baby names",
        f"Its share of US births climbed {share_change:,.0f} per 100,000 babies since 2020.",
    )


def falling_copy(name: str, share_change: float) -> tuple[str, str]:
    return (
        f"{name} is fading from its recent peak",
        f"Its share of US births fell {abs(share_change):,.0f} per 100,000 babies since 2020.",
    )


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    rising = pd.read_csv(PROCESSED_DIR / "rising.csv")
    falling = pd.read_csv(PROCESSED_DIR / "falling.csv")
    series = pd.read_csv(PROCESSED_DIR / "name_series.csv")
    out_dir = story_posts(SLUG)
    out_dir.mkdir(parents=True, exist_ok=True)

    cover = Slide(source=config["source"])
    cover.kicker("baby names")
    cover.title(config["title"])
    cover.dek(config["dek"])
    cover.save(out_dir / "ssa-name-trends-00-cover.png")

    for index, row in rising.iterrows():
        name = row["name"]
        title, dek = rising_copy(name, row["share_change"])
        subset = series[series["name"] == name]
        render_name_chart(
            subset,
            title=title,
            dek=dek,
            source=config["source"],
            output=out_dir / f"ssa-name-trends-rising-{index + 1:02d}.png",
        )

    for index, row in falling.iterrows():
        name = row["name"]
        title, dek = falling_copy(name, row["share_change"])
        subset = series[series["name"] == name]
        render_name_chart(
            subset,
            title=title,
            dek=dek,
            source=config["source"],
            output=out_dir / f"ssa-name-trends-falling-{index + 1:02d}.png",
        )

    print(f"Wrote 11 slides to {out_dir}")


if __name__ == "__main__":
    main()
