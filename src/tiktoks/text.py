"""Text measurement and wrapping against real glyph widths."""

from matplotlib.figure import Figure


def measure(figure: Figure, text: str, **font_kwargs) -> tuple[float, float]:
    """Return the pixel width and height of a single line of text."""
    artist = figure.text(0, 0, text, **font_kwargs)
    box = artist.get_window_extent(renderer=figure.canvas.get_renderer())
    artist.remove()
    return box.width, box.height


def wrap(figure: Figure, text: str, max_width: float, **font_kwargs) -> list[str]:
    """Greedy word wrap. Honors explicit newlines in the source text."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = [words[0]]
        for word in words[1:]:
            candidate = current + [word]
            width, _ = measure(figure, " ".join(candidate), **font_kwargs)
            if width > max_width:
                lines.append(" ".join(current))
                current = [word]
            else:
                current = candidate
        lines.append(" ".join(current))
    return lines


def fit(
    figure: Figure,
    text: str,
    max_width: float,
    *,
    size: int,
    min_size: int,
    max_lines: int,
    step: int = 2,
    **font_kwargs,
) -> tuple[list[str], int]:
    """Wrap text, shrinking the size until it fits the width and line budget."""
    current_size = size
    lines = wrap(figure, text, max_width, fontsize=current_size, **font_kwargs)
    while current_size - step >= min_size:
        widest = max(
            measure(figure, line, fontsize=current_size, **font_kwargs)[0] for line in lines
        )
        if len(lines) <= max_lines and widest <= max_width:
            break
        current_size -= step
        lines = wrap(figure, text, max_width, fontsize=current_size, **font_kwargs)
    return lines, current_size
