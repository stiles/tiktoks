"""Chart styling for one-off story slides."""

import matplotlib.ticker as mticker
from matplotlib.axes import Axes

from tiktoks.style import Theme, get_theme


def style_axes(
    ax: Axes,
    theme: Theme | str | None = None,
    *,
    grid: str = "y",
    tick_size: int = 24,
    y_ticks: int = 4,
) -> Axes:
    """Strip an axes down to a baseline, muted ticks and horizontal gridlines."""
    theme = get_theme(theme)
    ax.set_facecolor(theme.background)
    ax.grid(axis=grid, color=theme.border, linewidth=1, alpha=0.4)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.spines["bottom"].set_color(theme.border)
    ax.tick_params(axis="both", colors=theme.muted, labelsize=tick_size, length=0)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_fontfamily(theme.body_font)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(y_ticks))
    ax.set_xlabel("")
    ax.set_ylabel("")
    return ax


def label_end(
    ax: Axes,
    x,
    y,
    text: str,
    theme: Theme | str | None = None,
    *,
    color: str | None = None,
    size: int = 28,
    offset: float = 0.02,
) -> None:
    """Mark the last point of a line and label it, instead of using a legend."""
    theme = get_theme(theme)
    color = color or theme.highlight
    ax.scatter([x], [y], s=110, color=color, edgecolor=theme.background, linewidth=3, zorder=3)
    span = ax.get_xlim()[1] - ax.get_xlim()[0]
    ax.text(
        x + span * offset,
        y,
        text,
        color=theme.text,
        fontsize=size,
        fontweight="bold",
        fontfamily=theme.body_font,
        va="center",
        zorder=3,
    )
