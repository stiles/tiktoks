"""Geography loading, projection and plotting.

Projection happens in the `prepare_*` functions, which hand back a projected frame
and its bounds. Callers size the map box from those bounds before drawing, so a
world map is not squeezed into a portrait slot.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.patches import Circle
from shapely.ops import transform

from tiktoks.config import CROSSWALK_PATH, GIS_URLS, REFERENCE_DIR
from tiktoks.style import Theme, get_theme

WORLD_CRS = "+proj=eqearth +lon_0=0 +datum=WGS84 +units=m +no_defs"
NAME_COLUMNS = ("name", "name_long", "sovereignt", "NAME", "STATE_NAME")

# Country zooms get a window a few times wider than the country, so the shape sits
# in enough neighboring land to be recognizable. The floor keeps a microstate from
# filling the frame alone; the ceiling keeps a small country from becoming a dot.
CONTEXT_MULTIPLE = 4.0
MIN_SPAN_M = 250_000
MAX_SPAN_M = 1_100_000


def laea_crs(lon: float, lat: float) -> str:
    """Lambert azimuthal equal area centered on a point. Valid at any latitude."""
    return f"+proj=laea +lat_0={lat:.4f} +lon_0={lon:.4f} +datum=WGS84 +units=m +no_defs"


# Loading


def cached_path(url: str) -> Path:
    """Download a reference file once and read it from disk afterward."""
    local = REFERENCE_DIR / Path(url).name
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=180)
        response.raise_for_status()
        local.write_bytes(response.content)
    return local


@lru_cache(maxsize=16)
def read_geography(path_or_url: str) -> gpd.GeoDataFrame:
    source = str(path_or_url)
    if source.startswith("http"):
        source = str(cached_path(source))
    frame = gpd.read_file(source)
    if frame.crs is None:
        frame = frame.set_crs("EPSG:4326")
    return frame


def world_countries(path_or_url: str | Path | None = None) -> gpd.GeoDataFrame:
    return read_geography(str(path_or_url or GIS_URLS["countries"]))


def world_lines(path_or_url: str | Path | None = None) -> gpd.GeoDataFrame:
    return read_geography(str(path_or_url or GIS_URLS["country_lines"]))


def disputed_lines(path_or_url: str | Path | None = None) -> gpd.GeoDataFrame:
    return read_geography(str(path_or_url or GIS_URLS["disputed_lines"]))


def country_match(countries: gpd.GeoDataFrame, names: Iterable[str]) -> gpd.GeoDataFrame:
    """Match on the most specific name column that hits.

    Falling through to `sovereignt` would pull every dependency into the selection,
    so "United Kingdom" would return the Falklands and Pitcairn alongside Britain.
    """
    lookup = {name.casefold() for name in names}
    for column in (col for col in NAME_COLUMNS if col in countries.columns):
        mask = countries[column].astype(str).str.casefold().isin(lookup)
        if mask.any():
            return countries.loc[mask]
    raise ValueError(f"No feature matched: {', '.join(names)}")


def drop_antarctica(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    columns = [col for col in NAME_COLUMNS if col in frame.columns]
    if not columns:
        return frame
    mask = pd.Series(False, index=frame.index)
    for column in columns:
        mask = mask | frame[column].astype(str).str.casefold().eq("antarctica")
    return frame.loc[~mask]


# Projection


def center_of(frame: gpd.GeoDataFrame) -> tuple[float, float]:
    """Center longitude and latitude, corrected for shapes crossing the antimeridian."""
    min_x, min_y, max_x, max_y = frame.total_bounds
    if max_x - min_x > 180:
        shifted = frame.geometry.apply(lambda g: transform(lambda x, y: (x % 360, y), g))
        min_x, min_y, max_x, max_y = shifted.total_bounds
    lon = (min_x + max_x) / 2
    if lon > 180:
        lon -= 360
    return float(lon), float((min_y + max_y) / 2)


@dataclass
class MapView:
    """A projected frame plus the window to show it in."""

    base: gpd.GeoDataFrame
    bounds: tuple[float, float, float, float]
    target: gpd.GeoDataFrame | None = None

    @property
    def aspect(self) -> float:
        min_x, min_y, max_x, max_y = self.bounds
        return (max_x - min_x) / max(max_y - min_y, 1e-6)


def pad_bounds(bounds, pad: float, min_span: float = 0.0):
    min_x, min_y, max_x, max_y = bounds
    center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    width = max((max_x - min_x) * (1 + pad * 2), min_span)
    height = max((max_y - min_y) * (1 + pad * 2), min_span)
    return (
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    )


def core_parts(projected: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """The main landmass and its near neighbors, dropping distant outlying parts.

    Natural Earth folds overseas territory into the parent country, so Chile carries
    Easter Island and France carries French Guiana. Framing on the full extent would
    zoom out to an ocean. Outliers still draw; they just do not set the window.
    """
    parts = projected.explode(index_parts=False, ignore_index=True)
    if len(parts) < 2:
        return parts
    areas = parts.area
    largest = parts.geometry.iloc[areas.to_numpy().argmax()]
    radius = max(400_000.0, float(areas.max()) ** 0.5)
    near = parts[parts.distance(largest) <= radius]
    return near if not near.empty else parts


def prepare_country(
    countries: gpd.GeoDataFrame,
    names: Iterable[str],
    *,
    context: str = "regional",
    center: tuple[float, float] | None = None,
    zoom: float = 1.0,
) -> MapView:
    """Project the world around one country and return the window to draw."""
    selected = country_match(countries, names)

    if context == "world":
        base = drop_antarctica(countries).to_crs(WORLD_CRS)
        return MapView(base, tuple(pad_bounds(base.total_bounds, 0.01)), selected.to_crs(WORLD_CRS))

    # Find the main landmass in a rough projection of the selection alone, then
    # recenter on it before projecting the whole world.
    if center is None:
        rough = selected.to_crs(laea_crs(*center_of(selected)))
        core = core_parts(rough).to_crs("EPSG:4326")
        center = center_of(core)

    crs = laea_crs(*center)
    base = countries.to_crs(crs)
    target = selected.to_crs(crs)
    core = core_parts(target).total_bounds
    span = max(core[2] - core[0], core[3] - core[1])
    context = min(max(span * CONTEXT_MULTIPLE, MIN_SPAN_M), MAX_SPAN_M) * zoom
    return MapView(base, pad_bounds(core, 0.18, min_span=context), target)


def prepare_world(geography: gpd.GeoDataFrame, *, hide_antarctica: bool = True) -> MapView:
    frame = drop_antarctica(geography) if hide_antarctica else geography
    frame = frame.to_crs(WORLD_CRS)
    return MapView(frame, tuple(pad_bounds(frame.total_bounds, 0.01)))


# Drawing


def frame_axes(ax: Axes, bounds, aspect: float) -> None:
    """Center bounds in an axes of a given width/height ratio, filling it edge to edge."""
    min_x, min_y, max_x, max_y = bounds
    center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    if width / height < aspect:
        width = height * aspect
    else:
        height = width / aspect
    ax.set_xlim(center_x - width / 2, center_x + width / 2)
    ax.set_ylim(center_y - height / 2, center_y + height / 2)
    ax.set_aspect("equal")
    ax.set_axis_off()


# Share of the window the highlight has to fill before it can be found unaided.
# Measured across the country pool, the two island nations that need a ring sit at
# 0.0002 and the smallest country that does not (the Gambia) at 0.0085, so anything
# in between separates them. Bounding box does not work here: a scattered
# archipelago has a wide box and almost no ink in it.
LOCATOR_THRESHOLD = 0.002
LOCATOR_RADIUS = 0.07


def needs_locator(view: MapView, threshold: float = LOCATOR_THRESHOLD) -> bool:
    """Whether the highlighted country is too small to find unaided."""
    if view.target is None or view.target.empty:
        return False
    min_x, min_y, max_x, max_y = view.bounds
    window = max((max_x - min_x) * (max_y - min_y), 1e-6)
    return float(view.target.area.sum()) / window < threshold


def draw_highlight(
    ax: Axes,
    view: MapView,
    *,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    color: str | None = None,
    locator: bool = True,
) -> None:
    theme = get_theme(theme)
    ax.set_facecolor(theme.water)
    view.base.plot(ax=ax, color=theme.land, edgecolor=theme.border, linewidth=theme.map_line_width)
    view.target.plot(
        ax=ax,
        color=color or theme.highlight,
        edgecolor=(theme.highlight_edge_color or theme.text)
        if theme.highlight_edge_width
        else "none",
        linewidth=theme.highlight_edge_width,
    )
    frame_axes(ax, view.bounds, aspect)

    # A ring beats an inset for the cost. It keeps one map, one projection and one
    # shared rect across the prompt and the answer.
    if locator and needs_locator(view):
        left, right = ax.get_xlim()
        centroid = view.target.union_all().centroid
        ax.add_patch(
            Circle(
                (centroid.x, centroid.y),
                radius=(right - left) * LOCATOR_RADIUS,
                facecolor="none",
                edgecolor=color or theme.highlight,
                linewidth=3.5,
                zorder=4,
            )
        )


def draw_binary(
    ax: Axes,
    view: MapView,
    *,
    value_column: str,
    active_value=1,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    active_color: str | None = None,
) -> None:
    theme = get_theme(theme)
    fill = (
        view.base[value_column]
        .eq(active_value)
        .map({True: active_color or theme.highlight, False: theme.land})
    )
    ax.set_facecolor(theme.water)
    view.base.plot(ax=ax, color=fill, edgecolor=theme.border, linewidth=theme.map_line_width)
    frame_axes(ax, view.bounds, aspect)


def draw_choropleth(
    ax: Axes,
    view: MapView,
    *,
    value_column: str,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    scheme: str = "quantiles",
    bins: int | None = None,
) -> None:
    theme = get_theme(theme)
    colors = list(theme.sequential[: bins or len(theme.sequential)])
    ax.set_facecolor(theme.water)
    view.base.plot(
        ax=ax,
        column=value_column,
        cmap=ListedColormap(colors),
        scheme=scheme,
        k=len(colors),
        edgecolor=theme.border,
        linewidth=theme.map_line_width,
        missing_kwds={"color": theme.no_data, "edgecolor": theme.border},
        legend=False,
    )
    frame_axes(ax, view.bounds, aspect)


# Data


def join_values(
    geography: gpd.GeoDataFrame,
    values: pd.DataFrame,
    *,
    geo_key: str,
    data_key: str,
) -> gpd.GeoDataFrame:
    joined = geography.merge(values, left_on=geo_key, right_on=data_key, how="left")
    unmatched = set(values[data_key]) - set(geography[geo_key])
    if len(unmatched) > len(values) * 0.1:
        raise ValueError(f"Join dropped {len(unmatched)} rows. Check keys: {sorted(unmatched)[:8]}")
    return joined


@lru_cache(maxsize=1)
def country_crosswalk() -> pd.DataFrame:
    """Polygon name to ISO 3166-1 alpha-3 and Wikidata QID.

    Built by `scripts/build_crosswalk.py`. The boundary file carries no codes, so
    without this there is nothing to join a Wikidata or World Bank result to.
    """
    if not CROSSWALK_PATH.exists():
        raise FileNotFoundError(
            f"{CROSSWALK_PATH} is missing. Run: uv run python scripts/build_crosswalk.py"
        )
    return pd.read_csv(CROSSWALK_PATH, keep_default_na=False)


def with_codes(geography: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Add an `iso3` column to country polygons."""
    codes = country_crosswalk()[["name", "iso3"]]
    return geography.merge(codes, on="name", how="left")


def join_codes(
    geography: gpd.GeoDataFrame,
    values: pd.DataFrame,
    *,
    value_column: str,
    fill: float | int | None = None,
    min_coverage: float = 0.25,
) -> gpd.GeoDataFrame:
    """Join a frame keyed by ISO3 onto country polygons.

    Joining on codes rather than names is what makes an outside dataset usable
    without hand-editing its country column.
    """
    frame = with_codes(geography)
    incoming = values.drop_duplicates("iso3")[["iso3", value_column]]
    joined = frame.merge(incoming, on="iso3", how="left")
    if fill is not None:
        joined[value_column] = joined[value_column].fillna(fill)

    coverage = joined[value_column].notna().mean()
    if coverage < min_coverage:
        raise ValueError(
            f"Only {coverage:.0%} of polygons got a value for {value_column!r}. "
            "Check the ISO3 codes in the source data."
        )
    return joined


def quantile_edges(values: pd.Series, bins: int) -> list[float]:
    """Bin edges matching the quantile scheme, for labeling a legend."""
    clean = values.dropna()
    return [float(clean.quantile(index / bins)) for index in range(bins + 1)]
