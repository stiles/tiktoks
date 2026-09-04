"""Vertical-flow slide layout for 1080x1920 exports."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from tiktoks.config import CANVAS_SIZE  # noqa: E402
from tiktoks.paths import ensure_dir  # noqa: E402
from tiktoks.style import Theme, get_theme  # noqa: E402
from tiktoks.text import fit, measure  # noqa: E402

PT_TO_PX = 100 / 72


def shared_slot(*slides: "Slide", min_height: int = 620) -> tuple[float, float]:
    """The largest (top, height) map box that fits every slide passed in."""
    slots = [slide.content_slot() for slide in slides]
    top = max(slot[0] for slot in slots)
    bottom = min(slot[0] + slot[1] for slot in slots)
    return top, max(bottom - top, min_height)


class Slide:
    """Stacks a kicker, title and dek from the top, a footer from the bottom, and
    hands whatever vertical space is left to the map."""

    def __init__(
        self,
        theme: Theme | str | None = None,
        *,
        source: str | None = None,
        cue: str | None = None,
        badge: str | None = None,
        badge_color: str | None = None,
        width: int = CANVAS_SIZE[0],
        height: int = CANVAS_SIZE[1],
    ) -> None:
        self.theme = get_theme(theme)
        self.width = width
        self.height = height

        self.figure = plt.figure(
            figsize=(width / 100, height / 100),
            dpi=100,
            facecolor=self.theme.background,
        )
        self.canvas = self.figure.add_axes([0, 0, 1, 1], zorder=1)
        self.canvas.set_axis_off()
        self.canvas.set_xlim(0, width)
        self.canvas.set_ylim(height, 0)
        self.canvas.patch.set_visible(False)

        self.left = self.theme.margin_left
        self.right = width - self.theme.margin_right
        self.content_width = self.right - self.left
        self.cursor = self.theme.margin_top
        self.floor = height - self.theme.margin_bottom

        if badge:
            self._draw_badge(badge, badge_color or self.theme.highlight)
        if source:
            self._draw_source(source)
        if cue:
            self._draw_cue(cue)

    # Top-down blocks

    def kicker(self, text: str) -> None:
        if not text:
            return
        label = text.upper() if self.theme.kicker_upper else text
        self.canvas.text(
            self.left,
            self.cursor,
            label,
            color=self.theme.muted,
            fontsize=self.theme.kicker_size,
            fontweight="bold",
            fontfamily=self.theme.body_font,
            va="top",
        )
        self.cursor += self.theme.kicker_size * PT_TO_PX + self.theme.gap_kicker

    def title(self, text: str, *, hero: bool = False) -> None:
        if not text:
            return
        scale = self.theme.hero_scale if hero else 1.0
        font = {"fontfamily": self.theme.title_font, "fontweight": self.theme.title_weight}
        lines, size = fit(
            self.figure,
            text,
            self.content_width,
            size=int(self.theme.title_size * scale),
            min_size=self.theme.title_min_size,
            max_lines=self.theme.hero_lines if hero else self.theme.title_lines,
            **font,
        )
        self._draw_lines(lines, size, self.theme.title_leading, self.theme.text, font)
        self.cursor += self.theme.gap_title

    def dek(self, text: str) -> None:
        if not text:
            return
        font = {"fontfamily": self.theme.body_font, "fontweight": "normal"}
        lines, size = fit(
            self.figure,
            text,
            self.content_width,
            size=self.theme.dek_size,
            min_size=self.theme.dek_size - 8,
            max_lines=self.theme.dek_lines,
            **font,
        )
        self._draw_lines(lines, size, self.theme.dek_leading, self.theme.muted, font)
        self.cursor += self.theme.gap_dek

    # Map

    def map_axes(
        self,
        *,
        data_aspect: float | None = None,
        slot: tuple[float, float] | None = None,
        bleed: bool = False,
        min_height: int = 620,
    ) -> Axes:
        """Place a map axes between the last text block and the footer.

        `data_aspect` shrinks the box to the shape of the data rather than cropping
        it to a portrait slot, which matters for world maps. `slot` forces an exact
        (top, height) so a prompt and its answer share one frame. `bleed` runs the
        map to the slide edges.
        """
        if slot:
            top, height = slot
        else:
            top = self.cursor + self.theme.gap_map
            height = max(self.floor - top, min_height)

        left = 0 if bleed else self.left
        width = self.width if bleed else self.content_width

        if data_aspect:
            fitted = width / data_aspect
            if fitted < height:
                top += (height - fitted) / 2
                height = fitted

        if self.theme.map_panel and not bleed:
            self.canvas.add_patch(
                plt.Rectangle(
                    (left, top),
                    width,
                    height,
                    facecolor=self.theme.water,
                    edgecolor=self.theme.border,
                    linewidth=1.0,
                    zorder=0,
                )
            )

        axes = self.figure.add_axes(
            [
                left / self.width,
                1 - (top + height) / self.height,
                width / self.width,
                height / self.height,
            ],
            zorder=2,
        )
        axes.set_facecolor("none" if self.theme.map_panel else self.theme.background)
        axes.set_axis_off()
        axes.set_xticks([])
        axes.set_yticks([])
        self.map_aspect = width / height
        return axes

    def chart_axes(
        self,
        *,
        slot: tuple[float, float] | None = None,
        min_height: int = 520,
        gutter_left: int = 96,
        gutter_bottom: int = 70,
    ) -> Axes:
        """Place a chart axes between the last text block and the footer. The gutters
        leave room for tick labels, which matplotlib draws outside the data area."""
        top, height = slot or self.content_slot()
        height = max(height, min_height)
        axes = self.figure.add_axes(
            [
                (self.left + gutter_left) / self.width,
                1 - (top + height - gutter_bottom) / self.height,
                (self.content_width - gutter_left) / self.width,
                (height - gutter_bottom) / self.height,
            ],
            zorder=2,
        )
        axes.set_facecolor(self.theme.background)
        return axes

    def content_slot(self) -> tuple[float, float]:
        """The (top, height) the map would get right now. Use it to lock a pair of
        slides to one frame."""
        top = self.cursor + self.theme.gap_map
        return top, max(self.floor - top, 0)

    def legend(self, colors: list[str], labels: list[str], *, no_data: bool = False) -> None:
        """Bin strip above the footer, with a label at each end. Call before map_axes."""
        bar_height = 26
        step = self.content_width / len(colors)
        label_size = self.theme.source_size
        top = self.floor - bar_height - label_size * PT_TO_PX * 1.5

        for index, color in enumerate(colors):
            self.canvas.add_patch(
                plt.Rectangle(
                    (self.left + index * step, top),
                    step,
                    bar_height,
                    facecolor=color,
                    edgecolor=self.theme.background,
                    linewidth=1.5,
                    zorder=3,
                )
            )
        for x, label, align in ((self.left, labels[0], "left"), (self.right, labels[-1], "right")):
            self.canvas.text(
                x,
                top + bar_height + 12,
                label,
                color=self.theme.muted,
                fontsize=label_size,
                fontfamily=self.theme.body_font,
                ha=align,
                va="top",
            )
        if no_data:
            chip_top = top - 58
            self.canvas.add_patch(
                plt.Rectangle(
                    (self.left, chip_top),
                    bar_height,
                    bar_height,
                    facecolor=self.theme.no_data,
                    edgecolor=self.theme.border,
                    linewidth=1,
                    zorder=3,
                )
            )
            self.canvas.text(
                self.left + bar_height + 14,
                chip_top + bar_height / 2,
                "No data",
                color=self.theme.muted,
                fontsize=label_size,
                fontfamily=self.theme.body_font,
                va="center",
            )
            top = chip_top
        self.floor = top - 30

    # Bottom-up blocks

    def _draw_source(self, text: str) -> None:
        font = {"fontfamily": self.theme.body_font, "fontweight": "normal"}
        lines = fit(
            self.figure,
            text,
            self.content_width,
            size=self.theme.source_size,
            min_size=self.theme.source_size,
            max_lines=2,
            **font,
        )[0]
        leading = self.theme.source_size * PT_TO_PX * 1.28
        block = leading * len(lines)
        top = self.floor - block
        for index, line in enumerate(lines):
            self.canvas.text(
                self.left,
                top + index * leading,
                line,
                color=self.theme.muted,
                fontsize=self.theme.source_size,
                va="top",
                **font,
            )
        self.floor = top - 18

    def _draw_cue(self, text: str) -> None:
        size = self.theme.badge_size
        width, _ = measure(
            self.figure, text, fontsize=size, fontfamily=self.theme.body_font, fontweight="bold"
        )
        pad_x, pad_y = 30, 18
        box_height = size * PT_TO_PX + pad_y * 2
        top = self.floor - box_height
        self.canvas.add_patch(
            FancyBboxPatch(
                (self.left, top),
                width + pad_x * 2,
                box_height,
                boxstyle=f"round,pad=0,rounding_size={box_height / 2}",
                facecolor=self.theme.accent,
                edgecolor="none",
                zorder=3,
            )
        )
        self.canvas.text(
            self.left + pad_x + width / 2,
            top + box_height / 2,
            text,
            color=self.theme.badge_text,
            fontsize=size,
            fontweight="bold",
            fontfamily=self.theme.body_font,
            ha="center",
            va="center",
            zorder=4,
        )
        self.floor = top - 28

    def _draw_badge(self, text: str, color: str) -> None:
        size = self.theme.badge_size
        label = text.upper()
        width, _ = measure(
            self.figure, label, fontsize=size, fontfamily=self.theme.body_font, fontweight="bold"
        )
        pad_x, pad_y = 26, 14
        box_width = width + pad_x * 2
        box_height = size * PT_TO_PX + pad_y * 2
        top = self.theme.margin_top - pad_y
        self.canvas.add_patch(
            FancyBboxPatch(
                (self.right - box_width, top),
                box_width,
                box_height,
                boxstyle=f"round,pad=0,rounding_size={box_height / 2}",
                facecolor=color,
                edgecolor="none",
                zorder=3,
            )
        )
        self.canvas.text(
            self.right - box_width / 2,
            top + box_height / 2,
            label,
            color=self.theme.badge_text,
            fontsize=size,
            fontweight="bold",
            fontfamily=self.theme.body_font,
            ha="center",
            va="center",
            zorder=4,
        )

    # Internals

    def _draw_lines(
        self, lines: list[str], size: int, leading: float, color: str, font: dict
    ) -> None:
        step = size * PT_TO_PX * leading
        for index, line in enumerate(lines):
            self.canvas.text(
                self.left,
                self.cursor + index * step,
                line,
                color=color,
                fontsize=size,
                va="top",
                **font,
            )
        self.cursor += step * len(lines)

    def save(self, path: Path | str) -> Path:
        output = Path(path)
        ensure_dir(output.parent)
        self.figure.savefig(output, dpi=100, facecolor=self.figure.get_facecolor())
        plt.close(self.figure)
        return output
