"""Sequential color ramps for choropleths, from ColorBrewer.

House rule, from the graphics style guide: one hue, lightness carries the value,
light for low and dark for high. Two hues make a reader hunt for a category
boundary that is not there, so the multi-hue ColorBrewer ramps are deliberately
not here. Gray for no data stays outside the ramp, in `Theme.no_data`.

Values are the ColorBrewer six-class definitions. Six sits in the middle of the
five-to-seven bin range the style guide asks for. Other bin counts are
interpolated, which is close enough for a ramp that is read as an ordered scale
rather than matched swatch to swatch.
"""

from __future__ import annotations

from matplotlib.colors import LinearSegmentedColormap, to_hex

DEFAULT = "Blues"

SEQUENTIAL: dict[str, tuple[str, ...]] = {
    "Blues": ("#eff3ff", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"),
    "Greens": ("#edf8e9", "#c7e9c0", "#a1d99b", "#74c476", "#31a354", "#006d2c"),
    "Oranges": ("#feedde", "#fdd0a2", "#fdae6b", "#fd8d3c", "#e6550d", "#a63603"),
    "Purples": ("#f2f0f7", "#dadaeb", "#bcbddc", "#9e9ac8", "#756bb1", "#54278f"),
    "Reds": ("#fee5d9", "#fcbba1", "#fc9272", "#fb6a4a", "#de2d26", "#a50f15"),
    "Greys": ("#f7f7f7", "#d9d9d9", "#bdbdbd", "#969696", "#636363", "#252525"),
}


def sequential(name: str | None = None, bins: int = 6) -> list[str]:
    """A light-to-dark ramp of `bins` colors. The last color is the highest value."""
    key = name or DEFAULT
    try:
        base = SEQUENTIAL[key]
    except KeyError:
        raise ValueError(
            f"Unknown palette {key!r}. Options: {', '.join(sorted(SEQUENTIAL))}"
        ) from None
    if bins == len(base):
        return list(base)
    ramp = LinearSegmentedColormap.from_list(key, base)
    return [to_hex(ramp(index / (bins - 1))) for index in range(bins)]


def names() -> list[str]:
    return sorted(SEQUENTIAL)
