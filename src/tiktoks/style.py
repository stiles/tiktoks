"""Themes: color, type and spacing for a 1080x1920 slide."""

from dataclasses import dataclass, field, replace

# Every family listed here has to carry the weights the themes ask for. Matplotlib
# resolves the whole stack to build a fallback chain, not just the first hit, so a
# family missing a weight warns on every render even when it is never used.
# Plain "Avenir" has 300/400/500/800 and no 700, which is what warned on bold.
SANS = ("Avenir Next", "Helvetica Neue", "Arial", "DejaVu Sans")
CONDENSED = ("Barlow Condensed", "Archivo Narrow", "Arial Narrow", "DejaVu Sans")


@dataclass(frozen=True)
class Theme:
    name: str

    # Color
    background: str
    text: str
    muted: str
    border: str
    water: str
    land: str
    highlight: str
    accent: str
    no_data: str
    badge_text: str
    sequential: tuple[str, ...]

    # Type
    title_font: tuple[str, ...] = SANS
    body_font: tuple[str, ...] = SANS
    title_weight: str = "bold"
    title_size: int = 78
    title_min_size: int = 46
    title_lines: int = 3
    title_leading: float = 1.02
    # Hero titles carry world-map slides, where the map is 2:1 and leaves the top
    # third of the frame empty.
    hero_scale: float = 1.4
    hero_lines: int = 4
    dek_size: int = 36
    dek_lines: int = 3
    dek_leading: float = 1.3
    kicker_size: int = 28
    source_size: int = 22
    badge_size: int = 28
    kicker_upper: bool = True

    # Layout, in pixels on the 1080x1920 canvas
    margin_left: int = 88
    margin_right: int = 88
    margin_top: int = 120
    margin_bottom: int = 130
    gap_kicker: int = 26
    gap_title: int = 34
    gap_dek: int = 44
    gap_map: int = 40

    # Map treatment
    map_panel: bool = True
    map_line_width: float = 0.5
    highlight_edge_width: float = 1.6
    highlight_edge_color: str | None = None
    difficulty_colors: dict[str, str] = field(default_factory=dict)

    def color_for(self, difficulty: str) -> str:
        return self.difficulty_colors.get(difficulty, self.highlight)


PAPER = Theme(
    name="paper",
    background="#fbf7ef",
    text="#20201e",
    muted="#7a736a",
    border="#a89f92",
    water="#afc2d0",
    land="#e4dacb",
    highlight="#2f6f95",
    accent="#d66a3f",
    no_data="#dcd6cc",
    badge_text="#fbf7ef",
    sequential=("#e4eef4", "#bcd7e5", "#8ab8d0", "#5794b5", "#2f6f95", "#1d4c69"),
    difficulty_colors={
        "easy": "#2f6f95",
        "medium": "#7353a4",
        "hard": "#d66a3f",
        "expert": "#9b2f2f",
        "master": "#8a650b",
    },
)

NIGHT = Theme(
    name="night",
    background="#14171c",
    text="#f4f2ee",
    muted="#949ba6",
    border="#62707e",
    water="#181d24",
    land="#333c47",
    highlight="#4fd1c5",
    accent="#f6a623",
    no_data="#242a32",
    badge_text="#14171c",
    sequential=("#0f3b3d", "#14615c", "#1a877c", "#2aab9c", "#4fd1c5", "#a5f0e7"),
    map_line_width=0.7,
    # A dark rim reads as a gap between the highlight and its neighbors. A light one
    # fringes every island, which wrecks a coastline like Canada's.
    highlight_edge_width=1.2,
    highlight_edge_color="#14171c",
    difficulty_colors={
        "easy": "#4fd1c5",
        "medium": "#8ab4f8",
        "hard": "#f6a623",
        "expert": "#ff6b6b",
        "master": "#f2c14e",
    },
)

POSTER = Theme(
    name="poster",
    background="#101010",
    text="#ffffff",
    muted="#9a9a9a",
    border="#141414",
    water="#0b0b0b",
    land="#3d3d3d",
    highlight="#ffe000",
    accent="#ff4d3d",
    no_data="#242424",
    badge_text="#101010",
    sequential=("#4a3d00", "#7d6900", "#ae9400", "#dcbe00", "#ffe000", "#fff5a8"),
    title_font=CONDENSED,
    title_size=112,
    title_min_size=66,
    title_leading=0.92,
    title_lines=3,
    dek_size=34,
    kicker_size=30,
    map_panel=False,
    map_line_width=0.35,
    highlight_edge_width=0.0,
    difficulty_colors={
        "easy": "#ffe000",
        "medium": "#4ade80",
        "hard": "#ff9f1c",
        "expert": "#ff4d3d",
        "master": "#ffd166",
    },
)

THEMES = {theme.name: theme for theme in (NIGHT, PAPER, POSTER)}
DEFAULT_THEME = NIGHT


def get_theme(name: str | Theme | None) -> Theme:
    if isinstance(name, Theme):
        return name
    if not name:
        return DEFAULT_THEME
    try:
        return THEMES[name]
    except KeyError:
        raise ValueError(f"Unknown theme {name!r}. Options: {', '.join(sorted(THEMES))}") from None


def with_overrides(theme: Theme, overrides: dict | None) -> Theme:
    return replace(theme, **overrides) if overrides else theme
