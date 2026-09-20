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
import mapclassify
import numpy as np
import pandas as pd
import requests
from matplotlib.axes import Axes
from matplotlib.colors import ListedColormap
from matplotlib.patches import Circle
from shapely.ops import transform

from tiktoks.config import CROSSWALK_PATH, GIS_URLS, REFERENCE_DIR
from tiktoks.style import Theme, get_theme

WORLD_CRS = "+proj=eqearth +lon_0=0 +datum=WGS84 +units=m +no_defs"
US_ALBERS_CRS = "EPSG:5070"
NAME_COLUMNS = ("name", "name_long", "sovereignt", "NAME", "STATE_NAME")

# Country zooms get a window a few times wider than the country, so the shape sits
# in enough neighboring land to be recognizable. The floor keeps a microstate from
# filling the frame alone; the ceiling keeps a small country from becoming a dot.
CONTEXT_MULTIPLE = 4.0
MIN_SPAN_M = 250_000
MAX_SPAN_M = 1_100_000


# Lambert azimuthal equal area sends the antipode to infinity, so polygons on the
# far side of the globe project into the frame as enormous artifacts. Centered on
# Palau, the Atlantic washes the whole map flat. Drop anything past this angular
# distance from the center before projecting; nothing that far away can be visible.
MAX_ANGULAR_DEGREES = 140.0


def angular_distance(lon1, lat1, lon2: float, lat2: float):
    """Great-circle distance in degrees, vectorized over the first pair."""
    lon1, lat1 = np.radians(lon1), np.radians(lat1)
    lon2, lat2 = np.radians(lon2), np.radians(lat2)
    cosine = np.sin(lat1) * np.sin(lat2) + np.cos(lat1) * np.cos(lat2) * np.cos(lon1 - lon2)
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))


def near_center(
    frame: gpd.GeoDataFrame, center: tuple[float, float], within: float = MAX_ANGULAR_DEGREES
) -> gpd.GeoDataFrame:
    """Geometries close enough to the center to survive an azimuthal projection."""
    points = frame.geometry.representative_point()
    distance = angular_distance(points.x.to_numpy(), points.y.to_numpy(), center[0], center[1])
    return frame.loc[distance <= within]


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


@lru_cache(maxsize=1)
def _quiz_countries() -> gpd.GeoDataFrame:
    """Natural Earth 10m, with names compatible with existing quiz configs."""
    frame = read_geography(GIS_URLS["quiz_countries"]).copy()
    frame.columns = frame.columns.str.lower()
    # Preserve the source's long names while accepting historical pool match names.
    frame["name"] = frame["name"].replace(
        {"eSwatini": "Swaziland", "São Tomé and Principe": "Sao Tome and Principe"}
    )
    return frame


def quiz_countries(path_or_url: str | Path | None = None) -> gpd.GeoDataFrame:
    """Detailed quiz geometry; explicit custom sources retain their own schema."""
    if path_or_url is not None:
        return read_geography(str(path_or_url))
    return _quiz_countries()


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
    crs: str | None = None

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
    keep = parts.distance(largest) <= radius
    # Malaysia's peninsula and Borneo are both core regions, despite the sea
    # between them. Keep both when choosing the projection center and window.
    for column in (col for col in NAME_COLUMNS if col in parts.columns):
        keep |= parts[column].astype(str).str.casefold().eq("malaysia")
    near = parts[keep]
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
    base = near_center(countries, center).to_crs(crs)
    target = selected.to_crs(crs)
    core = core_parts(target).total_bounds
    span = max(core[2] - core[0], core[3] - core[1])
    context = min(max(span * CONTEXT_MULTIPLE, MIN_SPAN_M), MAX_SPAN_M) * zoom
    return MapView(base, pad_bounds(core, 0.18, min_span=context), target)


# Share of land area allowed to fall outside each side of a world map's frame.
#
# The full extent runs to the antimeridian, which spends the outer fifth of the
# width on equatorial Pacific. Trimming takes the aspect from 2.24 to 1.84 and the
# full-bleed height from 482px to 587px, so the continents get materially bigger.
#
# What that costs, measured in pixels on a 1080-wide render rather than as a share
# of each country: New Zealand keeps 99.7 percent and the United States 99.7. Every
# country clipped past that covers under 40 square pixels on screen — Fiji 24,
# Samoa 3, Kiribati 1 — which is below the size at which anything is visible or
# could inform an answer. They are still shaded; they sit outside the frame.
#
# Going further does have a real cost: at 0.002 New Zealand drops to 70 percent.
WORLD_TRIM = 0.0005


def ink_bounds(frame: gpd.GeoDataFrame, trim: float) -> tuple[float, float, float, float]:
    """Bounds holding all but `trim` of the land area on each side, horizontally.

    Vertical extent is left alone. The north is set by Greenland and the south by
    Tierra del Fuego, and both are real countries a reader will look for.
    """
    min_x, min_y, max_x, max_y = frame.total_bounds
    if trim <= 0:
        return min_x, min_y, max_x, max_y

    parts = frame.explode(index_parts=False, ignore_index=True)
    area = parts.area.to_numpy()
    total = area.sum()
    if total <= 0:
        return min_x, min_y, max_x, max_y
    edges = np.array([geometry.bounds for geometry in parts.geometry])

    def edge(values, ascending: bool) -> float:
        order = np.argsort(values)
        if not ascending:
            order = order[::-1]
        share = np.cumsum(area[order]) / total
        return float(values[order[min(int(np.searchsorted(share, trim)), len(order) - 1)]])

    return edge(edges[:, 0], True), min_y, edge(edges[:, 2], False), max_y


def prepare_world(
    geography: gpd.GeoDataFrame, *, hide_antarctica: bool = True, trim: float = WORLD_TRIM
) -> MapView:
    return prepare_world_projection(
        geography,
        WORLD_CRS,
        hide_antarctica=hide_antarctica,
        trim=trim,
    )


def prepare_world_projection(
    geography: gpd.GeoDataFrame,
    crs: str,
    *,
    hide_antarctica: bool = True,
    trim: float = WORLD_TRIM,
) -> MapView:
    """Project a world map into any CRS while reusing the standard framing rules."""
    frame = drop_antarctica(geography) if hide_antarctica else geography
    frame = frame.to_crs(crs)
    return MapView(frame, tuple(pad_bounds(ink_bounds(frame, trim), 0.01)), crs=crs)


def prepare_region(
    geography: gpd.GeoDataFrame,
    *,
    bounds: tuple[float, float, float, float] | None = None,
    crs: str = US_ALBERS_CRS,
    pad: float = 0.02,
) -> MapView:
    """Project a regional map, optionally framing a lon/lat bounding box.

    `bounds` is applied by representative point before projection. This keeps
    small outlying polygons from forcing a continental map to include Alaska,
    Hawaii or overseas territory, while retaining border counties that overlap
    the visible window.
    """
    frame = geography
    if bounds is not None:
        west, south, east, north = bounds
        lonlat = geography.to_crs("EPSG:4326")
        points = lonlat.geometry.representative_point()
        frame = lonlat.loc[
            points.x.between(west, east, inclusive="both")
            & points.y.between(south, north, inclusive="both")
        ]
        if frame.empty:
            raise ValueError("Regional bounds do not contain any geometry")
    frame = frame.to_crs(crs)
    return MapView(frame, tuple(pad_bounds(frame.total_bounds, pad)), crs=crs)


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
# Measured across the pool: Comoros 0.0002, San Marino 0.0011, Liechtenstein 0.0022
# and Seychelles 0.0028 all read as slivers at thumbnail size, while Malta 0.0044,
# Andorra 0.0071 and the Gambia 0.0085 are legible without help. The threshold sits
# in that gap. Bounding box does not work here: a scattered archipelago has a wide
# box and almost no ink in it.
LOCATOR_THRESHOLD = 0.0035
LOCATOR_RADIUS = 0.07


def needs_locator(view: MapView, threshold: float = LOCATOR_THRESHOLD) -> bool:
    """Whether the highlighted country is too small to find unaided."""
    if view.target is None or view.target.empty:
        return False
    min_x, min_y, max_x, max_y = view.bounds
    window = max((max_x - min_x) * (max_y - min_y), 1e-6)
    return float(view.target.area.sum()) / window < threshold


def prepare_outline(countries: gpd.GeoDataFrame, name: str) -> MapView:
    """Fit every part of a country, without regional framing or user zoom overrides."""
    selected = country_match(countries, [name])
    target = selected.to_crs(laea_crs(*center_of(selected)))
    return MapView(target, pad_bounds(target.total_bounds, 0.12), target)


def draw_outline(
    ax: Axes,
    view: MapView,
    *,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    color: str | None = None,
) -> None:
    """Draw only the target, with no neighboring land, borders or locator ring."""
    theme = get_theme(theme)
    ax.set_facecolor(theme.background)
    view.target.plot(ax=ax, color=color or theme.highlight, edgecolor="none")
    frame_axes(ax, view.bounds, aspect)


def draw_highlight(
    ax: Axes,
    view: MapView,
    *,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    color: str | None = None,
    locator: bool = True,
    borders: bool = True,
    border_color: str | None = None,
    border_width: float | None = None,
) -> None:
    theme = get_theme(theme)
    ax.set_facecolor(theme.water)
    view.base.plot(
        ax=ax,
        color=theme.land,
        edgecolor=(border_color or theme.border) if borders else "none",
        linewidth=(border_width if border_width is not None else theme.map_line_width)
        if borders
        else 0,
    )
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


def draw_backdrop(
    ax: Axes,
    view: MapView,
    *,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    zoom: float = 1.0,
) -> None:
    """A world map as wallpaper for a cover slide.

    A 2:1 world map fitted to a 9:16 frame is a thin band across the middle.
    `zoom` above 1 shrinks the window so the map takes more of the height, at the
    cost of cropping the far east and west. It is wallpaper, so the crop is fine.
    """
    theme = get_theme(theme)
    ax.set_facecolor(theme.water)
    view.base.plot(ax=ax, color=theme.land, edgecolor=theme.border, linewidth=theme.map_line_width)

    bounds = view.bounds
    if zoom != 1.0:
        min_x, min_y, max_x, max_y = bounds
        center_x, center_y = (min_x + max_x) / 2, (min_y + max_y) / 2
        half_w = (max_x - min_x) / 2 / zoom
        half_h = (max_y - min_y) / 2 / zoom
        bounds = (center_x - half_w, center_y - half_h, center_x + half_w, center_y + half_h)
    frame_axes(ax, bounds, aspect)


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
    colors: list[str] | None = None,
) -> None:
    """Bin a measure into a light-to-dark ramp. The last color is the highest bin."""
    theme = get_theme(theme)
    colors = list(colors or theme.sequential[: bins or len(theme.sequential)])
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


def draw_points(
    ax: Axes,
    view: MapView,
    points: gpd.GeoDataFrame,
    *,
    theme: Theme | str | None = None,
    aspect: float = 1.0,
    color: str | None = None,
    size: float = 20,
) -> None:
    """Draw point locations over a regional reference map."""
    theme = get_theme(theme)
    ax.set_facecolor(theme.water)
    view.base.plot(
        ax=ax,
        color=theme.land,
        edgecolor=theme.border,
        linewidth=theme.map_line_width,
    )
    projected = points.to_crs(view.crs or view.base.crs)
    projected.plot(
        ax=ax,
        color=color or theme.highlight,
        markersize=size,
        alpha=0.82,
        linewidth=0,
        zorder=3,
    )
    frame_axes(ax, view.bounds, aspect)


def draw_boundaries(
    ax: Axes,
    view: MapView,
    boundaries: gpd.GeoDataFrame,
    *,
    color: str,
    width: float = 1.2,
) -> None:
    """Overlay regional boundaries after a thematic polygon layer."""
    boundaries.to_crs(view.crs or view.base.crs).boundary.plot(
        ax=ax,
        color=color,
        linewidth=width,
        zorder=4,
    )


def derive_value(
    geography: gpd.GeoDataFrame,
    *,
    column: str,
    field: str | None = None,
    numerator: str | None = None,
    denominator: str | None = None,
) -> gpd.GeoDataFrame:
    """Add a numeric measure from one field or a numerator/denominator pair."""
    if field and (numerator or denominator):
        raise ValueError("Use either `field` or `numerator`/`denominator`, not both")
    if field:
        if field not in geography:
            raise ValueError(f"Geography has no field {field!r}")
        values = pd.to_numeric(geography[field], errors="coerce")
    elif numerator and denominator:
        missing = [name for name in (numerator, denominator) if name not in geography]
        if missing:
            raise ValueError(f"Geography has no field(s): {', '.join(missing)}")
        top = pd.to_numeric(geography[numerator], errors="coerce")
        bottom = pd.to_numeric(geography[denominator], errors="coerce")
        values = top.div(bottom.where(bottom.ne(0)))
    else:
        raise ValueError("A derived value needs `field` or `numerator` and `denominator`")
    return geography.assign(**{column: values})


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


def classification_edges(values: pd.Series, bins: int, scheme: str = "quantiles") -> list[float]:
    """Return legend endpoints from the same classifier used to draw the map."""
    clean = values.dropna()
    if clean.empty:
        raise ValueError("Cannot classify an empty value series")
    if scheme == "quantiles":
        return quantile_edges(clean, bins)
    classifier = mapclassify.classify(clean.to_numpy(), scheme=scheme, k=bins)
    return [float(clean.min()), *map(float, classifier.bins)]
