"""Vertical-flow slide layout for 1080x1920 exports."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from tiktoks import safe  # noqa: E402
from tiktoks.config import CANVAS_SIZE  # noqa: E402
from tiktoks.paths import ensure_dir  # noqa: E402
from tiktoks.safe import Box  # noqa: E402
from tiktoks.style import Theme, get_theme  # noqa: E402
from tiktoks.text import fit, measure  # noqa: E402

PT_TO_PX = 100 / 72

# The footer stack (legend, source, call-to-action) never runs taller than this, so
# the rail-clearance test can be done once instead of per element.
FOOTER_BAND = 420


def shared_slot(*slides: "Slide") -> tuple[float, float]:
    """The largest (top, height) map box that fits every slide passed in.

    This used to force a minimum height, which meant an overstuffed slide got a
    map taller than the space left for it. The map then ran over the legend, the
    source line and the call-to-action pill. A short map is a worse graphic; a map
    drawn on top of the legend is a broken one.
    """
    slots = [slide.content_slot() for slide in slides]
    top = max(slot[0] for slot in slots)
    bottom = min(slot[0] + slot[1] for slot in slots)
    return top, max(bottom - top, 0.0)


class Slide:
    """Stacks a kicker, title and dek from the top, a footer from the bottom, and
    hands whatever vertical space is left to the map.

    Margins are widened to clear TikTok's own interface. See `safe.py`; pass
    `safe_area=False` to lay out against the theme margins alone, which is only
    useful for style tests.
    """

    def __init__(
        self,
        theme: Theme | str | None = None,
        *,
        source: str | None = None,
        cue: str | None = None,
        badge: str | None = None,
        badge_color: str | None = None,
        safe_area: bool = True,
        width: int = CANVAS_SIZE[0],
        height: int = CANVAS_SIZE[1],
    ) -> None:
        self.theme = get_theme(theme)
        self.width = width
        self.height = height
        self.safe_area = safe_area
        self.map_aspect = 1.0

        self._texts: list[tuple[str, object]] = []
        self._boxes: list[tuple[str, Box]] = []
        self._map_rect: Box | None = None

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

        pad_left, pad_right, pad_top, pad_bottom = self._margins()
        self.left = pad_left
        self.right = width - pad_right
        self.content_width = self.right - self.left
        self.cursor = pad_top
        self.floor = height - pad_bottom

        # Content that sits low in the frame has to clear the button rail as well
        # as the caption band.
        self.footer_right = (
            safe.right_edge_at(self.floor - FOOTER_BAND, self.floor, self.right)
            if safe_area
            else self.right
        )

        if badge:
            self._draw_badge(badge, badge_color or self.theme.highlight)
        if source:
            self._draw_source(source)
        if cue:
            self._draw_cue(cue)

    def _margins(self) -> tuple[float, float, float, float]:
        theme = self.theme
        if not self.safe_area:
            return theme.margin_left, theme.margin_right, theme.margin_top, theme.margin_bottom
        return (
            max(theme.margin_left, safe.SIDE),
            max(theme.margin_right, safe.SIDE),
            max(theme.margin_top, safe.TOP),
            max(theme.margin_bottom, safe.BOTTOM),
        )

    # Top-down blocks

    def kicker(self, text: str) -> None:
        if not text:
            return
        label = text.upper() if self.theme.kicker_upper else text
        self._text(
            self.left,
            self.cursor,
            label,
            "kicker",
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
        lines, size = self._fit_block(
            text,
            size=int(self.theme.title_size * scale),
            min_size=self.theme.title_min_size,
            max_lines=self.theme.hero_lines if hero else self.theme.title_lines,
            leading=self.theme.title_leading,
            font=font,
        )
        self._draw_lines(lines, size, self.theme.title_leading, self.theme.text, font, "title")
        self.cursor += self.theme.gap_title

    def dek(self, text: str) -> None:
        if not text:
            return
        font = {"fontfamily": self.theme.body_font, "fontweight": "normal"}
        lines, size = self._fit_block(
            text,
            size=self.theme.dek_size,
            min_size=self.theme.dek_size - 8,
            max_lines=self.theme.dek_lines,
            leading=self.theme.dek_leading,
            font=font,
        )
        self._draw_lines(lines, size, self.theme.dek_leading, self.theme.muted, font, "dek")
        self.cursor += self.theme.gap_dek

    def _fit_block(
        self, text: str, *, size: int, min_size: int, max_lines: int, leading: float, font: dict
    ) -> tuple[list[str], int]:
        """Wrap to the content width, then rewrap narrower if the block would reach
        into the button rail. A long dek under a hero title lands in that band."""
        lines, fitted = fit(
            self.figure,
            text,
            self.content_width,
            size=size,
            min_size=min_size,
            max_lines=max_lines,
            **font,
        )
        if not self.safe_area:
            return lines, fitted
        block = fitted * PT_TO_PX * leading * len(lines)
        narrowed = safe.right_edge_at(self.cursor, self.cursor + block, self.right) - self.left
        if narrowed >= self.content_width:
            return lines, fitted
        return fit(
            self.figure,
            text,
            narrowed,
            size=size,
            min_size=min_size,
            max_lines=max_lines,
            **font,
        )

    # Cover slides

    def backdrop_axes(self) -> tuple[Axes, float]:
        """A full-canvas axes behind everything, for a cover slide's map.

        The map here is wallpaper, not information. It runs edge to edge and takes
        a scrim over it so the text stays readable.
        """
        axes = self.figure.add_axes([0, 0, 1, 1], zorder=0)
        axes.set_axis_off()
        axes.set_xticks([])
        axes.set_yticks([])
        return axes, self.width / self.height

    def scrim(self, alpha: float = 0.62, color: str | None = None) -> None:
        """Wash the backdrop toward the background color so type reads over it."""
        self.canvas.add_patch(
            plt.Rectangle(
                (0, 0),
                self.width,
                self.height,
                facecolor=color or self.theme.background,
                edgecolor="none",
                alpha=alpha,
                zorder=0,
            )
        )

    def centered_stack(
        self, blocks: list[dict], *, top: float | None = None, bottom: float | None = None
    ) -> None:
        """Center a stack of text blocks in the band between `top` and `bottom`.

        The normal flow is left-aligned and top-down. A cover reads better centered,
        so this measures the whole stack first and then places it.

        The default band stops above the button rail rather than at the footer.
        Centered type runs to both edges, so a headline that reaches the rail's
        vertical band collides with it, and narrowing a cover headline enough to
        squeeze past the rail shrinks it to nothing.
        """
        top = self.cursor if top is None else top
        if bottom is None:
            bottom = min(self.floor, safe.RAIL_TOP - 24) if self.safe_area else self.floor
        center_x = (self.left + self.right) / 2

        measured = []
        total = 0.0
        for block in blocks:
            font = {
                "fontfamily": block.get("font", self.theme.body_font),
                "fontweight": block.get("weight", "normal"),
            }
            lines, size = fit(
                self.figure,
                block["text"],
                self.content_width,
                size=block["size"],
                min_size=block.get("min_size", block["size"]),
                max_lines=block.get("max_lines", 3),
                **font,
            )
            leading = block.get("leading", 1.15)
            height = size * PT_TO_PX * leading * len(lines)
            measured.append((block, lines, size, leading, height, font))
            total += height + block.get("gap_after", 0)

        cursor = top + max((bottom - top - total) / 2, 0)
        for block, lines, size, leading, height, font in measured:
            step = size * PT_TO_PX * leading
            for index, line in enumerate(lines):
                self._text(
                    center_x,
                    cursor + index * step,
                    line,
                    block.get("kind", "cover"),
                    color=block.get("color", self.theme.text),
                    fontsize=size,
                    ha="center",
                    va="top",
                    **font,
                )
            cursor += height + block.get("gap_after", 0)

    # Map and chart

    def map_axes(
        self,
        *,
        data_aspect: float | None = None,
        slot: tuple[float, float] | None = None,
        bleed: bool = False,
        min_height: int = 620,
    ) -> tuple[Axes, float]:
        """Place a map axes between the last text block and the footer.

        Returns the axes and its width/height ratio, which the `draw_*` helpers
        need in order to fill the box instead of letterboxing inside it.

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
            # Fit the data inside the slot on both axes. Shrinking only the height
            # meant a slot shorter than the data cropped the map instead of scaling
            # it, which sliced the top and bottom off a world map.
            fitted_height = width / data_aspect
            if fitted_height <= height:
                top += (height - fitted_height) / 2
                height = fitted_height
            else:
                fitted_width = height * data_aspect
                left += (width - fitted_width) / 2
                width = fitted_width

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
        self._map_rect = Box(left, top, left + width, top + height)
        self.map_aspect = width / height
        return axes, self.map_aspect

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
        span = self.footer_right - self.left
        step = span / len(colors)
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
        self._record("legend bar", Box(self.left, top, self.footer_right, top + bar_height))
        for x, label, align in (
            (self.left, labels[0], "left"),
            (self.footer_right, labels[-1], "right"),
        ):
            self._text(
                x,
                top + bar_height + 12,
                label,
                "legend label",
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
            self._text(
                self.left + bar_height + 14,
                chip_top + bar_height / 2,
                "No data",
                "no-data chip",
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
            self.footer_right - self.left,
            size=self.theme.source_size,
            min_size=self.theme.source_size,
            max_lines=2,
            **font,
        )[0]
        leading = self.theme.source_size * PT_TO_PX * 1.28
        # Measure the last line rather than assuming it is one leading tall. The
        # leading estimate ignores glyph descent, which pushed the source a few
        # pixels into the caption band.
        _, line_height = measure(self.figure, "Hgy", fontsize=self.theme.source_size, **font)
        block = leading * (len(lines) - 1) + line_height
        top = self.floor - block
        for index, line in enumerate(lines):
            self._text(
                self.left,
                top + index * leading,
                line,
                "source",
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
        self._record(
            "cue pill", Box(self.left, top, self.left + width + pad_x * 2, top + box_height)
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
        top = self.cursor
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
        self._record("badge", Box(self.right - box_width, top, self.right, top + box_height))
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
        # The text stack starts below the badge rather than beside it, so a long
        # headline can never run into it.
        self.cursor = top + box_height + 22

    # Layout checking

    def _text(self, x: float, y: float, label: str, kind: str, **kwargs):
        artist = self.canvas.text(x, y, label, **kwargs)
        self._texts.append((kind, artist))
        return artist

    def _record(self, kind: str, box: Box) -> None:
        self._boxes.append((kind, box))

    def boxes(self) -> list[tuple[str, Box]]:
        """Every text run and interface chip the slide drew, in slide coordinates."""
        renderer = self.figure.canvas.get_renderer()
        found = list(self._boxes)
        for kind, artist in self._texts:
            extent = artist.get_window_extent(renderer=renderer)
            # Display coordinates put the origin at the bottom left; slide
            # coordinates put it at the top left.
            found.append(
                (kind, Box(extent.x0, self.height - extent.y1, extent.x1, self.height - extent.y0))
            )
        return found

    def check_layout(self) -> list[str]:
        """Text or chips that land where TikTok's interface will cover them.

        A pixel scan would flag world maps, which bleed to the canvas edge on
        purpose, so the check runs on element bounds instead.
        """
        problems = []
        if self.safe_area:
            for kind, box in self.boxes():
                for zone in safe.collisions(box):
                    problems.append(
                        f"{kind} at ({box.x0:.0f}, {box.y0:.0f})-({box.x1:.0f}, {box.y1:.0f}) "
                        f"overlaps the {zone}"
                    )
        # A map drawn over the legend or the source line is the other way this
        # breaks, and no safe zone catches it.
        if self._map_rect is not None:
            for kind, box in self.boxes():
                if kind.startswith("cover"):
                    continue
                if box.intersects(self._map_rect, tolerance=6.0):
                    problems.append(f"the map overlaps the {kind}")
        return problems

    # Internals

    def _draw_lines(
        self, lines: list[str], size: int, leading: float, color: str, font: dict, kind: str
    ) -> None:
        step = size * PT_TO_PX * leading
        for index, line in enumerate(lines):
            self._text(
                self.left,
                self.cursor + index * step,
                line,
                kind,
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
