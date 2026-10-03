"""Six slides: the cover, why October is still summer, then how hot this September ran."""

import json
from dataclasses import replace
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import pandas as pd

from tiktoks.charts import style_axes
from tiktoks.io import read_yaml
from tiktoks.paths import story_data, story_posts
from tiktoks.post import Post
from tiktoks.slides import Slide
from tiktoks.style import INTER, get_theme

HERE = Path(__file__).resolve().parent
THEME = replace(get_theme("night"), title_font=INTER, body_font=INTER)
plt.rcParams["font.family"] = list(INTER)

HOT = "#f28b50"
BAR = "#4a5562"
BAND = "#262d36"
HALO = [pe.withStroke(linewidth=8, foreground=THEME.background)]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SUMMER_MONTHS = {7, 8, 9, 10}


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def ap_date(text: str) -> str:
    date = pd.Timestamp(text)
    month = {3: "March", 4: "April", 5: "May", 6: "June", 7: "July", 9: "Sept."}.get(
        date.month, date.strftime("%b.")
    )
    return f"{month} {date.day}, {date.year}"


def slide(config: dict, source: str, title: str, dek: str | None = None) -> Slide:
    page = Slide(THEME, source=source)
    page.kicker(config["kicker"])
    page.title(title)
    page.dek(dek)
    return page


def clean(axes, *, grid: str | None = "y"):
    style_axes(axes, THEME, grid=grid or "y")
    if grid is None:
        axes.grid(False)
    return axes


def cover(config: dict) -> Slide:
    page = Slide(THEME)
    page.kicker(config["kicker"])
    page.title(config["title"] + ".", hero=True)
    page.dek(config["cover_dek"], color=HOT, weight="semibold")
    return page


def normals_slide(config: dict, source: str, data: Path) -> Slide:
    table = pd.read_csv(data / "month_normals.csv").set_index("month")
    start, end = config["normals"]
    rank = int(table.loc[10, "rank_hi"])
    page = slide(
        config,
        source,
        config["normals_title"].format(rank=ordinal(rank)),
        config["normals_dek"].format(start=start, end=end),
    )
    axes = clean(
        page.chart_axes(gutter_left=80, gutter_bottom=10, gutter_right=page.rail_gutter()),
        grid=None,
    )
    for month, row in table.iterrows():
        hot = month in SUMMER_MONTHS
        axes.barh(
            month, row["hi"] - row["lo"], left=row["lo"], height=0.66, color=HOT if hot else BAR
        )
        axes.text(
            row["lo"] - 1.2,
            month,
            f"{row['lo']:.0f}°",
            ha="right",
            va="center",
            fontsize=22,
            color=THEME.muted,
        )
        axes.text(
            row["hi"] + 1.2,
            month,
            f"{row['hi']:.0f}°",
            va="center",
            fontsize=26,
            color=THEME.text,
            fontweight="bold" if hot else "normal",
        )
        if hot:
            axes.text(
                row["hi"] + 8.5,
                month,
                f"#{int(row['rank_hi'])}",
                va="center",
                fontsize=26,
                fontweight="bold",
                color=HOT,
            )
    axes.set_yticks(range(1, 13), MONTHS)
    for label in axes.get_yticklabels():
        hot = MONTHS.index(label.get_text()) + 1 in SUMMER_MONTHS
        label.set_color(THEME.text if hot else THEME.muted)
        label.set_fontsize(26)
    axes.set_ylim(12.6, 0.4)
    axes.set_xlim(40, 100)
    axes.set_xticks([])
    axes.spines["bottom"].set_visible(False)
    return page


def hottest_slide(config: dict, source: str, data: Path, facts: dict) -> Slide:
    page = slide(config, source, config["hottest_title"], config["hottest_dek"])
    top, height = page.content_slot()
    right = page.right - page.rail_gutter()
    label_w, gap = 70, 40
    panel_w = (right - page.left - label_w - gap) / 2
    for index, (key, station) in enumerate(config["stations"].items()):
        share = pd.read_csv(data / f"hottest_month_{key}.csv").set_index("month")["share"]
        x0 = page.left + label_w + index * (panel_w + gap)
        y0 = top + 90
        axes = page.figure.add_axes(
            [
                x0 / page.width,
                1 - (top + height) / page.height,
                panel_w / page.width,
                (top + height - y0) / page.height,
            ],
            zorder=2,
        )
        clean(axes, grid=None)
        fall = share.index.isin([9, 10])
        axes.barh(share.index, share.values, height=0.7, color=[HOT if f else BAR for f in fall])
        for month, value in share.items():
            if value >= 0.005:
                axes.text(
                    value + 0.015,
                    month,
                    f"{value:.0%}",
                    va="center",
                    fontsize=22,
                    color=THEME.text,
                    fontweight="bold" if month in (9, 10) else "normal",
                )
        axes.set_ylim(12.6, 0.4)
        axes.set_xlim(0, 0.52)
        axes.set_xticks([])
        axes.set_yticks(range(1, 13), MONTHS if index == 0 else [])
        for label in axes.get_yticklabels():
            label.set_fontsize(22)
        axes.spines["bottom"].set_visible(False)
        axes.axvline(0, color=THEME.border, linewidth=1)
        axes.set_title(
            f"{station['name']}\n{facts['hottest_day_years'][key]} years",
            loc="left",
            fontsize=24,
            fontweight="bold",
            color=THEME.text,
            pad=16,
            linespacing=1.3,
        )
    return page


def summer_slide(config: dict, source: str, data: Path, facts: dict) -> Slide:
    df = pd.read_csv(data / "summer_lax.csv", parse_dates=["date"])
    page = slide(
        config, source, config["summer_title"], config["summer_dek"].format(year=config["year"])
    )
    axes = clean(page.chart_axes(gutter_left=80, gutter_right=page.rail_gutter()))
    axes.fill_between(
        df["date"], df["normal_lo"], df["normal_hi"], step="mid", color=BAND, linewidth=0, zorder=1
    )
    above = df["hi"] > df["normal_hi"]
    axes.bar(
        df["date"],
        df["hi"] - df["lo"],
        bottom=df["lo"],
        width=0.72,
        color=[HOT if a else BAR for a in above],
        zorder=2,
    )
    peak = df.loc[df["hi"].idxmax()]
    axes.annotate(
        f"{peak['hi']:.0f}° on Sept. {peak['date'].day}",
        (peak["date"], peak["hi"]),
        xytext=(-14, -4),
        textcoords="offset points",
        ha="right",
        va="top",
        fontsize=24,
        fontweight="bold",
        color=THEME.text,
        path_effects=HALO,
        zorder=4,
    )
    for row, (color, label) in enumerate(
        [(HOT, "High above normal"), (BAR, "High at or below normal"), (BAND, "Normal range")]
    ):
        y = 0.15 - row * 0.055
        axes.add_patch(
            plt.Rectangle(
                (0.01, y - 0.016), 0.035, 0.032, color=color, transform=axes.transAxes, zorder=4
            )
        )
        axes.text(
            0.065,
            y,
            label,
            transform=axes.transAxes,
            va="center",
            fontsize=20,
            color=THEME.text,
            zorder=4,
        )
    axes.set_ylim(46, 102)
    axes.set_yticks([60, 70, 80, 90, 100], ["60", "70", "80", "90", "100°"])
    end = df["date"].max()
    axes.set_xlim(df["date"].min() - pd.Timedelta(days=2), end + pd.Timedelta(days=2))
    ticks = pd.date_range(df["date"].min(), end, freq="MS")
    axes.set_xticks(
        ticks,
        [
            {7: "July", 8: "Aug.", 9: "Sept.", 10: "Oct."}.get(t.month, t.strftime("%b."))
            for t in ticks
        ],
    )
    axes.tick_params(axis="x", colors=THEME.text)
    return page


def septembers_slide(config: dict, source: str, data: Path, facts: dict) -> Slide:
    sep = pd.read_csv(data / "septembers_lax.csv")
    year = config["year"]
    start, end = config["normals"]
    top = sep.nlargest(10, "departure").iloc[::-1]
    page = Slide(THEME, source=source)
    page.kicker(config["kicker"])
    page.title(config["septembers_title"])
    page.dek(
        config["septembers_dek"].format(first=facts["september_first_year"], start=start, end=end)
    )
    page.dek(
        f"{year} ranks No. {facts['september_rank']} of {facts['september_years']}",
        color=HOT,
        weight="semibold",
    )
    axes = clean(
        page.chart_axes(gutter_left=100, gutter_bottom=10, gutter_right=page.rail_gutter()),
        grid=None,
    )
    is_year = top["year"] == year
    axes.barh(
        range(len(top)), top["departure"], height=0.66, color=[HOT if y else BAR for y in is_year]
    )
    for position, (_, row) in enumerate(top.iterrows()):
        this = row["year"] == year
        axes.text(
            row["departure"] + 0.12,
            position,
            f"+{row['departure']:.1f}°",
            va="center",
            fontsize=26,
            color=THEME.text,
            fontweight="bold" if this else "normal",
        )
    axes.set_yticks(range(len(top)), top["year"].astype(int))
    for label in axes.get_yticklabels():
        this = label.get_text() == str(year)
        label.set_fontsize(26)
        label.set_color(THEME.text if this else THEME.muted)
        label.set_fontweight("bold" if this else "normal")
    axes.set_xlim(0, top["departure"].max() * 1.3)
    axes.set_xticks([])
    axes.spines["bottom"].set_visible(False)
    axes.axvline(0, color=THEME.border, linewidth=1)
    return page


def nights_slide(config: dict, source: str, data: Path, facts: dict) -> Slide:
    sep = pd.read_csv(data / "septembers_lax.csv")
    year = config["year"]
    start, end = config["normals"]
    page = slide(
        config,
        source,
        config["nights_title"],
        config["nights_dek"].format(threshold=config["warm_night"]),
    )
    axes = clean(page.chart_axes(gutter_left=130, gutter_right=page.rail_gutter()))
    axes.bar(
        sep["year"],
        sep["warm_nights"],
        width=0.8,
        color=[HOT if y == year else BAR for y in sep["year"]],
        zorder=2,
    )
    base = facts["warm_nights_normal"]
    axes.axhline(base, color=THEME.text, linewidth=2, linestyle=(0, (4, 3)), zorder=3)
    axes.text(
        sep["year"].min() + 1,
        base + 0.5,
        f"{start}–{end} average: {base:.0f}",
        fontsize=22,
        color=THEME.text,
        va="bottom",
        path_effects=HALO,
        zorder=4,
    )
    nights = facts["warm_nights"]
    axes.annotate(
        f"{year}: {nights}",
        (year, nights),
        xytext=(0, 12),
        textcoords="offset points",
        ha="right",
        fontsize=26,
        fontweight="bold",
        color=HOT,
        path_effects=HALO,
        zorder=4,
    )
    peak = int(sep["warm_nights"].max())
    ymax = (peak // 5 + 1) * 5
    axes.set_ylim(0, ymax + 1)
    axes.set_yticks(
        range(0, ymax + 1, 5),
        [str(t) if t < ymax else f"{t} nights" for t in range(0, ymax + 1, 5)],
    )
    axes.set_xlim(sep["year"].min() - 2, year + 1.5)
    axes.set_xticks([1940, 1960, 1980, 2000, 2020])
    axes.tick_params(axis="x", colors=THEME.text)
    return page


def main() -> None:
    config = read_yaml(HERE / "story.yaml")
    data = story_data(config["slug"]) / "processed"
    facts = json.loads((data / "facts.json").read_text(encoding="utf-8"))
    source = f"{config['source']} Data through {ap_date(facts['through'])}."
    year = config["year"]

    post = Post(
        slug=config["slug"],
        format="story",
        theme=THEME,
        output_dir=story_posts(config["slug"]),
        topic=config["topic"],
        title=config["title"],
        caption=config.get("caption"),
        hashtags=config["hashtags"],
        sources=[source],
        config_path=HERE / "story.yaml",
    )
    post.add(
        cover(config),
        kind="cover",
        title=config["title"],
        alt="Title slide: October isn't fall in LA.",
    )
    post.add(
        normals_slide(config, source, data),
        kind="story",
        title=config["normals_title"],
        alt="Range bars of average daily highs and lows by month in downtown LA, "
        "with July through October highlighted.",
    )
    post.add(
        hottest_slide(config, source, data, facts),
        kind="story",
        title=config["hottest_title"],
        alt="Bar charts of the month in which each year's hottest day fell, downtown "
        "and at LAX. September and October lead.",
    )
    post.add(
        summer_slide(config, source, data, facts),
        kind="story",
        title=config["summer_title"],
        alt=f"Daily high-low bars at LAX since July {year} against the normal range, "
        f"peaking at {facts['peak_high']} degrees.",
    )
    post.add(
        septembers_slide(config, source, data, facts),
        kind="story",
        title=config["septembers_title"],
        alt=f"The 10 warmest Septembers at LAX; {year} ranks No. {facts['september_rank']}.",
    )
    post.add(
        nights_slide(config, source, data, facts),
        kind="story",
        title=config["nights_title"],
        alt=f"Warm September nights at LAX by year; {year} had {facts['warm_nights']}.",
    )
    post.finish()
    print(f"Wrote {len(post.paths)} slides to {post.output_dir}")


if __name__ == "__main__":
    main()
