"""Framing and joining rules that are easy to break and hard to see."""

import pandas as pd
import pytest

from tiktoks.catalog import _patch, _verify
from tiktoks.maps import (
    country_match,
    drop_antarctica,
    pad_bounds,
    prepare_country,
    prepare_world,
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
