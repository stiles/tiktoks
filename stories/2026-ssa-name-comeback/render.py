from pathlib import Path

import matplotlib.ticker as mticker
import pandas as pd

from tiktoks.charts import label_end, style_axes
from tiktoks.io import read_yaml
from tiktoks.slides import Slide

HERE = Path(__file__).resolve().parent
PROCESSED_DIR = HERE / "data" / "processed"


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    series = pd.read_csv(PROCESSED_DIR / "name_series.csv")
    latest = series.iloc[-1]

    slide = Slide(source=config["source"])
    slide.kicker("baby names")
    slide.title(config["title"])
    slide.dek(config["dek"])

    axes = slide.chart_axes()
    theme = slide.theme
    axes.plot(series["year"], series["share_per_100k"], color=theme.highlight, linewidth=6)
    style_axes(axes, theme)
    axes.yaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    axes.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:.0f}"))
    # Room on the right for the end label, which replaces a legend.
    first, last = int(series["year"].min()), int(series["year"].max())
    axes.set_xlim(first, last + 42)
    # Stop the ticks at the data; the trailing space only holds the label.
    axes.set_xticks(range(1900, last + 1, 25))
    label_end(
        axes,
        latest["year"],
        latest["share_per_100k"],
        f"{latest['share_per_100k']:.1f}\nper 100k",
        theme,
        size=26,
    )

    slide.save(HERE / config.get("output_dir", "output") / "ssa-name-comeback-01.png")


if __name__ == "__main__":
    main()
