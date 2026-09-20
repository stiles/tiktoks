"""Framing and joining rules that are easy to break and hard to see."""

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from tiktoks.catalog import _patch, _verify
from tiktoks.maps import (
    classification_edges,
    country_match,
    derive_value,
    drop_antarctica,
    pad_bounds,
    prepare_country,
    prepare_outline,
    prepare_region,
    prepare_world,
    prepare_world_projection,
    quantile_edges,
    with_codes,
    world_countries,
)


@pytest.fixture(scope="module")
def countries():
    return world_countries()


def test_match_uses_the_most_specific_name_column(countries):
    """Falling through to `sovereignt` returns the Falklands alongside Britain."""
    matched = country_match(countries, ["United Kingdom"])
    assert len(matched) == 1
    assert "Falkland" not in " ".join(matched["name"])


def test_match_raises_rather_than_returning_nothing(countries):
    with pytest.raises(ValueError, match="No feature matched"):
        country_match(countries, ["Atlantis"])


def test_country_framing_ignores_distant_territory(countries):
    """Natural Earth folds Easter Island into Chile. Framing on the full extent
    would zoom out to an ocean."""
    view = prepare_country(countries, ["Chile"])
    min_x, _, max_x, _ = view.bounds
    assert max_x - min_x < 3_000_000


def test_microstates_keep_some_neighboring_land(countries):
    view = prepare_country(countries, ["Lesotho"])
    min_x, min_y, max_x, max_y = view.bounds
    assert max(max_x - min_x, max_y - min_y) >= 250_000


def test_antarctica_is_dropped(countries):
    assert len(drop_antarctica(countries)) < len(countries)
    assert "Antarctica" not in set(drop_antarctica(countries)["name"])


def test_pad_bounds_respects_a_minimum_span():
    bounds = pad_bounds((0, 0, 10, 10), 0.1, min_span=500)
    assert bounds[2] - bounds[0] == 500


def test_quantile_edges_span_the_data():
    edges = quantile_edges(pd.Series([1, 2, 3, 4, 5]), 4)
    assert len(edges) == 5
    assert edges[0] == 1 and edges[-1] == 5


def test_fisher_jenks_edges_match_the_data_range():
    edges = classification_edges(pd.Series([1, 2, 3, 30, 31, 32]), 3, "FisherJenks")
    assert len(edges) == 4
    assert edges[0] == 1 and edges[-1] == 32


def test_derived_value_supports_fields_and_shares():
    geography = gpd.GeoDataFrame(
        {"group": [20, 30], "total": [100, 0], "average": [2.4, 3.1]},
        geometry=[box(-100, 30, -99, 31), box(-99, 30, -98, 31)],
        crs="EPSG:4326",
    )
    shares = derive_value(geography, column="value", numerator="group", denominator="total")
    averages = derive_value(geography, column="value", field="average")
    assert list(shares["value"].dropna()) == [0.2]
    assert shares["value"].isna().iloc[1]
    assert list(averages["value"]) == [2.4, 3.1]


def test_regional_framing_drops_outlying_geometry():
    geography = gpd.GeoDataFrame(
        geometry=[box(-100, 30, -99, 31), box(-157, 20, -156, 21)],
        crs="EPSG:4326",
    )
    view = prepare_region(geography, bounds=(-125, 24, -66, 50))
    assert len(view.base) == 1
    assert view.crs == "EPSG:5070"


def test_crosswalk_codes_most_countries(countries):
    coded = with_codes(countries)
    # Uncoded polygons carry an empty string, not NaN, so count non-empty.
    assert coded["iso3"].str.len().eq(3).mean() > 0.9
    lookup = coded.set_index("name")["iso3"]
    assert lookup["United States"] == "USA"
    assert lookup["China"] == "CHN"


def test_places_without_an_iso_code_still_appear(countries):
    """Kosovo and Western Sahara have no ISO 3166-1 code but are real polygons."""
    coded = with_codes(countries)
    assert "Kosovo" in set(coded["name"])
    assert coded.loc[coded["name"] == "Kosovo", "iso3"].iloc[0] == ""


def test_patch_applies_include_and_exclude():
    frame = pd.DataFrame({"iso3": ["FRA", "AGO"], "member": [1, 1]})
    patched = _patch(frame, {"include": ["dnk"], "exclude": ["AGO"]}, "member")
    assert set(patched["iso3"]) == {"FRA", "DNK"}


def test_verify_rejects_an_unexpected_count():
    frame = pd.DataFrame({"iso3": ["FRA"], "member": [1]})
    with pytest.raises(ValueError, match="expected 32"):
        _verify(frame, {"slug": "nato", "expect": {"count": 32}}, "member")
    _verify(frame, {"slug": "nato", "expect": {"count": 1}}, "member")


def test_verify_accepts_a_floor():
    frame = pd.DataFrame({"iso3": ["FRA", "DEU"], "member": [1, 1]})
    with pytest.raises(ValueError, match="at least 5"):
        _verify(frame, {"slug": "x", "expect": {"min_countries": 5}}, "member")


def test_far_side_of_the_globe_is_dropped_before_projecting(countries):
    """LAEA sends the antipode to infinity, so far-side polygons project into the
    frame as artifacts. Centered on Palau, they washed the whole map flat."""
    view = prepare_country(countries, ["Palau"], zoom=14)
    names = set(view.base["name"])
    assert "Philippines" in names
    assert "Brazil" not in names


def test_a_normal_country_keeps_its_neighbors(countries):
    """The antipodal filter must not cost an ordinary map its context."""
    view = prepare_country(countries, ["Japan"])
    # The boundary file names these "Korea" and "Dem. Rep. Korea".
    assert {"Korea", "China", "Russia"} <= set(view.base["name"])
    assert len(view.base) > len(countries) * 0.9


def test_world_trim_keeps_every_country_that_is_visible(countries):
    """The trim buys map by dropping empty Pacific. It must not cost a country
    anyone could see: at 1080px wide, everything it clips is under 40 square
    pixels, while New Zealand and the United States stay essentially whole."""
    from shapely.geometry import box

    view = prepare_world(countries)
    low, high = view.bounds[0], view.bounds[2]
    scale = 1080 / (high - low)
    window = box(low, -9e6, high, 9e6)

    kept = {}
    for _, row in view.base.iterrows():
        area = row.geometry.area
        if area:
            kept[row["name"]] = (row.geometry.intersection(window).area / area, area * scale**2)

    assert kept["New Zealand"][0] > 0.99
    assert kept["United States"][0] > 0.99
    clipped = [(name, px) for name, (share, px) in kept.items() if share < 0.9]
    assert clipped, "the trim should be doing something"
    assert max(px for _, px in clipped) < 40


def test_world_trim_can_be_switched_off(countries):
    assert prepare_world(countries, trim=0).aspect > prepare_world(countries).aspect


def test_custom_world_projection_changes_the_world_frame(countries):
    equal_earth = prepare_world(countries)
    mercator = prepare_world_projection(countries, "EPSG:3395")
    assert mercator.crs == "EPSG:3395"
    assert mercator.aspect < equal_earth.aspect


def test_outline_fits_all_parts_and_draws_no_context(countries):
    import matplotlib.pyplot as plt

    from tiktoks.maps import draw_outline

    # Chile includes distant islands that regional framing intentionally ignores.
    view = prepare_outline(countries, "Chile")
    left, bottom, right, top = view.bounds
    x0, y0, x1, y1 = view.target.total_bounds
    assert left < x0 < x1 < right
    assert bottom < y0 < y1 < top
    fig, ax = plt.subplots()
    try:
        draw_outline(ax, view, aspect=0.8)
        assert len(ax.collections) == 1  # target only, no regional base layer
        assert len(ax.patches) == 0  # no locator circle
        assert ax.get_xlim()[0] <= x0 and ax.get_xlim()[1] >= x1
        assert ax.get_ylim()[0] <= y0 and ax.get_ylim()[1] >= y1
    finally:
        plt.close(fig)


def test_quiz_boundaries_are_detailed_and_keep_legacy_names(countries):
    from shapely import get_num_coordinates

    from tiktoks.maps import quiz_countries

    detailed = quiz_countries()
    for name in ("Swaziland", "Sao Tome and Principe", "Guinea-Bissau", "Tajikistan"):
        target = country_match(detailed, [name])
        assert len(target) == 1
        assert (
            get_num_coordinates(target.geometry).sum()
            > get_num_coordinates(country_match(countries, [name]).geometry).sum()
        )
    assert len(country_match(detailed, ["Eswatini"])) == 1
    # Loading quiz data must not rename columns in the cached original source.
    from tiktoks.config import GIS_URLS
    from tiktoks.maps import read_geography

    assert "NAME" in read_geography(GIS_URLS["quiz_countries"]).columns


def test_quiz_custom_boundary_file_is_respected(tmp_path, countries):
    from tiktoks.maps import quiz_countries

    path = tmp_path / "custom.geojson"
    country_match(countries, ["Italy"]).to_file(path, driver="GeoJSON")
    custom = quiz_countries(path)
    assert len(custom) == 1
    assert custom.iloc[0]["name"] == "Italy"
