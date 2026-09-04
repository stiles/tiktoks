from pathlib import Path

from tiktoks.charts import style_axes
from tiktoks.slides import Slide

HERE = Path(__file__).resolve().parent


def main() -> None:
    slide = Slide(source="Source: Add source.")
    slide.kicker("data story")
    slide.title("Story title")
    slide.dek("One sentence on what the chart shows.")

    axes = style_axes(slide.chart_axes(), slide.theme)
    axes.plot([], [])

    slide.save(HERE / "output" / "story-01.png")


if __name__ == "__main__":
    main()
